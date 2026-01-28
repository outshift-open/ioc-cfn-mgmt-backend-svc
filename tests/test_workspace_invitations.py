"""
Tests for workspace invitation and member management endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta


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
        assert member["user_id"] == "dev-user"  # Default dev user from get_current_user
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
