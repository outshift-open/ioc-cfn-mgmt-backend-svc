"""
Tests for automatic default workspace creation during user signup.
Verifies that multiple users can have workspaces with the same name.
"""
import pytest
from fastapi.testclient import TestClient

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.workspace import Workspace as WorkspaceModel
from server.database.relational_db.models.workspace_member import (
    WorkspaceMember as WorkspaceMemberModel,
)
from server.main import app


@pytest.fixture
def unauthenticated_client(setup_test_environment):
    """Create a test client without authentication headers."""
    return TestClient(app)


class TestSignupDefaultWorkspace:
    """Test cases for default workspace creation during signup."""

    def test_two_users_signup_with_same_workspace_name_succeeds(self, unauthenticated_client):
        """
        Test that two different users can sign up and each gets a default workspace
        with the same name ("Default Workspace"), and both signups succeed.

        This verifies that workspace names don't need to be globally unique,
        and each user can have their own workspace with the same name.
        """
        # User A signs up
        response_user_a = unauthenticated_client.post("/api/auth/signup", json={
            "username": "user_a",
            "email": "user_a@example.com",
            "password": "SecurePassword123",
        })

        assert response_user_a.status_code == 201, f"User A signup failed: {response_user_a.json()}"
        data_user_a = response_user_a.json()

        # Verify User A received tokens and user data
        assert "access_token" in data_user_a
        assert "refresh_token" in data_user_a
        assert data_user_a["token_type"] == "bearer"
        assert "user" in data_user_a
        assert data_user_a["user"]["username"] == "user_a"

        user_a_id = data_user_a["user"]["id"]
        user_a_token = data_user_a["access_token"]

        # User B signs up
        response_user_b = unauthenticated_client.post("/api/auth/signup", json={
            "username": "user_b",
            "email": "user_b@example.com",
            "password": "SecurePassword123",
        })

        assert response_user_b.status_code == 201, f"User B signup failed: {response_user_b.json()}"
        data_user_b = response_user_b.json()

        # Verify User B received tokens and user data
        assert "access_token" in data_user_b
        assert "refresh_token" in data_user_b
        assert data_user_b["token_type"] == "bearer"
        assert "user" in data_user_b
        assert data_user_b["user"]["username"] == "user_b"

        user_b_id = data_user_b["user"]["id"]
        user_b_token = data_user_b["access_token"]

        # Verify both users have different IDs
        assert user_a_id != user_b_id, "User IDs should be unique"

        # Verify User A has a default workspace
        response_workspaces_a = unauthenticated_client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {user_a_token}"}
        )
        assert response_workspaces_a.status_code == 200
        workspaces_a = response_workspaces_a.json()["workspaces"]

        assert len(workspaces_a) == 1, f"User A should have exactly 1 workspace, found {len(workspaces_a)}"
        assert workspaces_a[0]["name"] == "Default Workspace", f"Expected 'Default Workspace', got '{workspaces_a[0]['name']}'"
        workspace_a_id = workspaces_a[0]["id"]

        # Verify User B has a default workspace
        response_workspaces_b = unauthenticated_client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {user_b_token}"}
        )
        assert response_workspaces_b.status_code == 200
        workspaces_b = response_workspaces_b.json()["workspaces"]

        assert len(workspaces_b) == 1, f"User B should have exactly 1 workspace, found {len(workspaces_b)}"
        assert workspaces_b[0]["name"] == "Default Workspace", f"Expected 'Default Workspace', got '{workspaces_b[0]['name']}'"
        workspace_b_id = workspaces_b[0]["id"]

        # Verify both workspaces have the same name but different IDs
        assert workspaces_a[0]["name"] == workspaces_b[0]["name"], "Both workspaces should have the same name"
        assert workspace_a_id != workspace_b_id, "Workspace IDs should be unique"

        # Verify in database that both workspaces exist with the same name
        db = RelationalDB()
        session = db.get_session()
        try:
            workspace_a_db = session.query(WorkspaceModel).filter(
                WorkspaceModel.id == workspace_a_id
            ).first()
            workspace_b_db = session.query(WorkspaceModel).filter(
                WorkspaceModel.id == workspace_b_id
            ).first()

            assert workspace_a_db is not None, "User A's workspace not found in database"
            assert workspace_b_db is not None, "User B's workspace not found in database"
            assert workspace_a_db.name == "Default Workspace"
            assert workspace_b_db.name == "Default Workspace"
            assert workspace_a_db.created_by == user_a_id
            assert workspace_b_db.created_by == user_b_id

            # Verify workspace membership
            member_a = session.query(WorkspaceMemberModel).filter(
                WorkspaceMemberModel.workspace_id == workspace_a_id,
                WorkspaceMemberModel.user_id == user_a_id
            ).first()
            member_b = session.query(WorkspaceMemberModel).filter(
                WorkspaceMemberModel.workspace_id == workspace_b_id,
                WorkspaceMemberModel.user_id == user_b_id
            ).first()

            assert member_a is not None, "User A should be a member of their workspace"
            assert member_a.role == "admin", "User A should be admin of their workspace"
            assert member_b is not None, "User B should be a member of their workspace"
            assert member_b.role == "admin", "User B should be admin of their workspace"

        finally:
            session.close()

    def test_user_signup_creates_default_workspace_with_correct_name(self, unauthenticated_client):
        """Test that a single user signup creates exactly one default workspace with the correct name."""
        response = unauthenticated_client.post("/api/auth/signup", json={
            "username": "single_user",
            "email": "single_user@example.com",
            "password": "SecurePassword123",
        })

        assert response.status_code == 201
        data = response.json()
        user_id = data["user"]["id"]
        token = data["access_token"]

        # List workspaces for the user
        workspaces_response = unauthenticated_client.get(
            "/api/workspaces/",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert workspaces_response.status_code == 200
        workspaces = workspaces_response.json()["workspaces"]

        # Verify exactly one workspace was created
        assert len(workspaces) == 1
        assert workspaces[0]["name"] == "Default Workspace"

    def test_multiple_sequential_signups_each_get_default_workspace(self, unauthenticated_client):
        """Test that multiple users signing up sequentially each get their own default workspace."""
        users = []

        # Create 5 different users
        for i in range(5):
            username = f"user_{i}"
            response = unauthenticated_client.post("/api/auth/signup", json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "SecurePassword123",
            })

            assert response.status_code == 201, f"Signup failed for {username}"
            data = response.json()
            users.append({
                "id": data["user"]["id"],
                "username": username,
                "token": data["access_token"]
            })

        # Verify each user has exactly one default workspace
        workspace_names = []
        workspace_ids = set()

        for user in users:
            response = unauthenticated_client.get(
                "/api/workspaces/",
                headers={"Authorization": f"Bearer {user['token']}"}
            )

            assert response.status_code == 200
            workspaces = response.json()["workspaces"]

            assert len(workspaces) == 1, f"User {user['username']} should have exactly 1 workspace"
            workspace = workspaces[0]

            workspace_names.append(workspace["name"])
            workspace_ids.add(workspace["id"])

            # Verify workspace is named "Default Workspace"
            assert workspace["name"] == "Default Workspace"

        # Verify all workspaces have the same name
        assert all(name == "Default Workspace" for name in workspace_names), \
            "All default workspaces should have the same name"

        # Verify all workspace IDs are unique
        assert len(workspace_ids) == 5, \
            f"Expected 5 unique workspace IDs, got {len(workspace_ids)}"
