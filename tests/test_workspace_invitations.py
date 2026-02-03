"""
Tests for workspace invitation and member management endpoints.
"""
from datetime import datetime, timedelta, timezone

import pytest


class TestWorkspaceInvitationFlow:
    """Test cases for workspace invitation and member management."""

    def test_create_workspace_auto_adds_creator_as_admin(self, client, admin_user):
        """Test that workspace creator is automatically added as admin member."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        assert response.status_code == 201
        workspace_id = response.json()["id"]

        # Verify creator is a member with admin role
        response = client.get(f"/api/workspaces/{workspace_id}/members")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["members"]) == 1
        member = data["members"][0]
        assert member["user_id"] == "dev-user"  # Default dev user from get_auth_user
        assert member["role"] == "admin"
        assert member["workspace_id"] == workspace_id

    def test_admin_can_invite_user(self, client, admin_user, test_user):
        """Test that admin can invite a user to workspace."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        assert response.status_code == 201
        workspace_id = response.json()["id"]

        # Invite user
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        assert response.status_code == 201
        invitation_id = response.json()["id"]
        assert isinstance(invitation_id, str)

    def test_invite_nonexistent_user_fails(self, client):
        """Test that inviting nonexistent user fails."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Try to invite nonexistent user
        invitation_data = {
            "invitee_username": "nonexistent_user",
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_invite_invalid_role_fails(self, client, test_user):
        """Test that inviting with invalid role fails."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Try to invite with invalid role
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "invalid_role"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        assert response.status_code == 422

    def test_list_workspace_invitations(self, client, test_user):
        """Test listing invitations for a workspace."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Create invitation
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        invitation_id = response.json()["id"]

        # List invitations
        response = client.get(f"/api/workspaces/{workspace_id}/invitations")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["invitations"]) == 1
        invitation = data["invitations"][0]
        assert invitation["id"] == invitation_id
        assert invitation["invitee_username"] == test_user["username"]
        assert invitation["role"] == "viewer"
        assert invitation["status"] == "pending"
        assert "workspace_name" in invitation
        assert "inviter_username" in invitation
        assert "expires_at" in invitation

    def test_get_pending_invitations(self, client, test_user):
        """Test getting pending invitations for current user."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Create invitation for test_user
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )

        # Get pending invitations (would be from test_user's perspective in real scenario)
        # Note: In this test, dev-user is the one calling, so they won't see this invitation
        response = client.get("/api/invitations/pending")
        assert response.status_code == 200
        # Dev-user has no invitations
        assert response.json()["total"] == 0

    def test_cancel_invitation(self, client, test_user):
        """Test admin can cancel a pending invitation."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Create invitation
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        invitation_id = response.json()["id"]

        # Cancel invitation
        response = client.delete(
            f"/api/workspaces/{workspace_id}/invitations/{invitation_id}"
        )
        assert response.status_code == 204

        # Verify invitation is gone from list
        response = client.get(f"/api/workspaces/{workspace_id}/invitations")
        assert response.json()["total"] == 0

    def test_duplicate_invitation_fails(self, client, test_user):
        """Test that creating duplicate pending invitation fails."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Create first invitation
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        assert response.status_code == 201

        # Try to create duplicate invitation
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_accept_invitation_returns_assigned_role(self, client, admin_user, test_user):
        """Test that accepting an invitation returns workspace details and assigned role."""
        import hashlib

        from fastapi.testclient import TestClient

        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.api_key import ApiKey as ApiKeyModel
        from server.main import app

        # Create an API key for test_user
        db = RelationalDB()
        session = db.session_factory()
        try:
            raw_api_key = "ioc_test_user_api_key_12345678901234567890123456"
            hashed_key = hashlib.sha256(raw_api_key.encode()).hexdigest()
            key_preview = raw_api_key[:20]  # First 20 chars for preview

            api_key = ApiKeyModel(
                user_id=test_user["id"],
                name="Test API Key",
                key_hash=hashed_key,
                key_preview=key_preview,
            )
            session.add(api_key)
            session.commit()
        finally:
            session.close()

        # Create workspace as admin
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        assert response.status_code == 201
        workspace_id = response.json()["id"]

        # Invite test_user with viewer role
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )
        assert response.status_code == 201
        invitation_id = response.json()["id"]

        # Accept invitation as test_user
        test_user_client = TestClient(app)
        test_user_client.headers = {"X-API-Key": raw_api_key}

        response = test_user_client.post(f"/api/invitations/{invitation_id}/accept")
        assert response.status_code == 200

        # Verify response includes workspace details and assigned role
        data = response.json()
        assert "message" in data
        assert data["message"] == "Invitation accepted successfully"
        assert "workspace_id" in data
        assert data["workspace_id"] == workspace_id
        assert "workspace_name" in data
        assert data["workspace_name"] == "Test Workspace"
        assert "assigned_role" in data
        assert data["assigned_role"] == "viewer"

        # Verify test_user can now see the workspace (viewers can list workspaces)
        workspaces_response = test_user_client.get("/api/workspaces/")
        assert workspaces_response.status_code == 200
        workspaces = workspaces_response.json()["workspaces"]
        assert len(workspaces) == 1
        assert workspaces[0]["id"] == workspace_id


class TestWorkspaceMemberManagement:
    """Test cases for workspace member management."""

    def test_list_workspace_members(self, client):
        """Test listing workspace members."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # List members
        response = client.get(f"/api/workspaces/{workspace_id}/members")
        assert response.status_code == 200
        data = response.json()

        # Creator should be auto-added as admin
        assert data["total"] == 1
        assert data["members"][0]["role"] == "admin"
        assert data["members"][0]["is_creator"] is True

    def test_update_member_role(self, client, test_user):
        """Test updating a member's role."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Manually add test_user as viewer
        from server.services.workspace_member import workspace_member_service
        workspace_member_service.add_member(
            workspace_id=workspace_id,
            user_id=test_user["id"],
            role="viewer",
            created_by="dev-user"
        )

        # Update role to admin
        response = client.put(
            f"/api/workspaces/{workspace_id}/members/{test_user['id']}",
            json={"role": "admin"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["user_id"] == test_user["id"]

    def test_remove_member(self, client, test_user):
        """Test removing a member from workspace."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Manually add test_user
        from server.services.workspace_member import workspace_member_service
        workspace_member_service.add_member(
            workspace_id=workspace_id,
            user_id=test_user["id"],
            role="viewer",
            created_by="dev-user"
        )

        # Remove member
        response = client.delete(
            f"/api/workspaces/{workspace_id}/members/{test_user['id']}"
        )
        assert response.status_code == 204

        # Verify member is removed
        response = client.get(f"/api/workspaces/{workspace_id}/members")
        members = response.json()["members"]
        member_ids = [m["user_id"] for m in members]
        assert test_user["id"] not in member_ids

    def test_admin_cannot_remove_self(self, client):
        """Test that admin cannot remove themselves."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Try to remove self (dev-user is the creator/admin)
        response = client.delete(
            f"/api/workspaces/{workspace_id}/members/dev-user"
        )
        assert response.status_code == 403
        assert "cannot remove yourself" in response.json()["detail"].lower()

    def test_is_creator_flag_in_member_list(self, client, test_user):
        """Test that is_creator flag correctly identifies workspace creator."""
        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.workspace_member import (
            WorkspaceMember,
        )

        # Create workspace as dev-user
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Add test_user as a member (not creator)
        db = RelationalDB()
        session = db.session_factory()
        try:
            member = WorkspaceMember(
                workspace_id=workspace_id,
                user_id=test_user["id"],
                role="admin",
                created_by="dev-user",
            )
            session.add(member)
            session.commit()
        finally:
            session.close()

        # List members
        response = client.get(f"/api/workspaces/{workspace_id}/members")
        assert response.status_code == 200
        members = response.json()["members"]

        # Should have 2 members
        assert len(members) == 2

        # Find dev-user and test_user
        dev_user_member = next((m for m in members if m["user_id"] == "dev-user"), None)
        test_user_member = next((m for m in members if m["user_id"] == test_user["id"]), None)

        assert dev_user_member is not None
        assert test_user_member is not None

        # dev-user is creator, test_user is not
        assert dev_user_member["is_creator"] is True
        assert test_user_member["is_creator"] is False


class TestWorkspaceInvitationExpiration:
    """Test cases for invitation expiration."""

    def test_invitation_has_expiration_date(self, client, test_user):
        """Test that created invitations have expiration dates."""
        # Create workspace
        response = client.post("/api/workspaces/", json={"name": "Test Workspace"})
        workspace_id = response.json()["id"]

        # Create invitation
        invitation_data = {
            "invitee_username": test_user["username"],
            "role": "viewer"
        }
        response = client.post(
            f"/api/workspaces/{workspace_id}/invitations",
            json=invitation_data
        )

        # Get invitation details
        response = client.get(f"/api/workspaces/{workspace_id}/invitations")
        invitation = response.json()["invitations"][0]

        # Verify expiration is approximately 7 days from now
        expires_at_str = invitation["expires_at"]
        # Handle both ISO format with Z and without timezone
        if expires_at_str.endswith("Z"):
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        else:
            expires_at = datetime.fromisoformat(expires_at_str)
            # If naive, assume UTC
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(days=7)

        # Allow 1 minute tolerance for test execution time
        time_diff = abs((expires_at - expected_expiry).total_seconds())
        assert time_diff < 60, "Expiration should be approximately 7 days from creation"
