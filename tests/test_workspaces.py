"""
Tests for workspace endpoints in ioc-cfn-mgmt-backend.
"""
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.api_key import ApiKey
from server.database.relational_db.models.user import User
from server.database.relational_db.models.workspace_member import WorkspaceMember
from server.main import app


class TestWorkspaceEndpoints:
    """Test cases for workspace management endpoints."""

    def test_create_workspace_success(self, client, sample_workspace_data):
        """Test successful workspace creation."""
        response = client.post("/api/workspaces", json=sample_workspace_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert isinstance(data["id"], str)
        import uuid

        uuid.UUID(data["id"])

    def test_create_workspace_invalid_data(self, client):
        """Test workspace creation with invalid data."""
        response = client.post("/api/workspaces", json={})
        assert response.status_code == 422

        response = client.post("/api/workspaces", json={"name": ""})
        assert response.status_code == 422

    def test_create_workspace_invalid_json(self, client):
        """Test workspace creation with invalid JSON."""
        response = client.post("/api/workspaces", content="invalid json", headers={"Content-Type": "application/json"})
        assert response.status_code == 422

    def test_list_workspaces_empty(self, client):
        """Test listing workspaces when none exist."""
        response = client.get("/api/workspaces")

        assert response.status_code == 200
        data = response.json()
        assert "workspaces" in data
        assert data["workspaces"] == []

    def test_list_workspaces_with_data(self, client, sample_workspace_data):
        """Test listing workspaces after creating some."""
        create_response = client.post("/api/workspaces", json=sample_workspace_data)
        assert create_response.status_code == 201
        workspace_id = create_response.json()["id"]

        list_response = client.get("/api/workspaces")
        assert list_response.status_code == 200

        data = list_response.json()
        assert "workspaces" in data
        assert len(data["workspaces"]) == 1

        workspace = data["workspaces"][0]
        assert workspace["id"] == workspace_id
        assert workspace["name"] == sample_workspace_data["name"]
        assert "created_at" in workspace

    def test_list_workspaces_multiple(self, client):
        """Test listing multiple workspaces."""
        workspaces_data = [{"name": "Workspace 1"}, {"name": "Workspace 2"}, {"name": "Workspace 3"}]

        created_ids = []
        for ws_data in workspaces_data:
            response = client.post("/api/workspaces", json=ws_data)
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        response = client.get("/api/workspaces")
        assert response.status_code == 200

        data = response.json()
        assert len(data["workspaces"]) == 3

        returned_ids = [ws["id"] for ws in data["workspaces"]]
        for created_id in created_ids:
            assert created_id in returned_ids

    def test_get_workspace_by_id(self, client, created_workspace, sample_workspace_data):
        """Test getting a specific workspace by ID."""
        response = client.get(f"/api/workspaces/{created_workspace}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_workspace
        assert data["name"] == sample_workspace_data["name"]
        assert "created_at" in data

    def test_get_workspace_not_found(self, client):
        """Test getting a workspace that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/workspaces/{fake_id}")

        assert response.status_code == 404

    def test_get_workspace_invalid_id(self, client):
        """Test getting a workspace with invalid ID format."""
        response = client.get("/api/workspaces/invalid-id")

        assert response.status_code == 404

    def test_delete_workspace_blocked_then_succeeds(self, client, sample_workspace_data):
        """Workspace delete should be blocked with dependents, then succeed after cleanup."""
        ws_resp = client.post("/api/workspaces", json=sample_workspace_data)
        assert ws_resp.status_code == 201
        workspace_id = ws_resp.json()["id"]

        mas_data = {
            "name": "WS-Del Test MAS",
            "description": "",
            "agents": {"a1": {"type": "t"}},
            "config": {},
        }
        mas_resp = client.post(f"/api/workspaces/{workspace_id}/multi-agentic-systems", json=mas_data)
        assert mas_resp.status_code == 201
        mas_id = mas_resp.json()["id"]

        # Attempt to delete workspace should be blocked (409) due to dependents
        del_ws_resp_blocked = client.delete(f"/api/workspaces/{workspace_id}")
        assert del_ws_resp_blocked.status_code == 409
        assert "Workspace has dependent objects" in del_ws_resp_blocked.json()["detail"]

        # Delete dependents first
        del_mas_resp = client.delete(f"/api/workspaces/{workspace_id}/multi-agentic-systems/{mas_id}")
        assert del_mas_resp.status_code == 204

        # Workspace delete succeeds
        del_ws_resp_ok = client.delete(f"/api/workspaces/{workspace_id}")
        assert del_ws_resp_ok.status_code == 204

    def test_delete_default_workspace_public_forbidden(self, client):
        """Public delete of Default Workspace should be forbidden (403)."""
        create_resp = client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert create_resp.status_code == 201
        default_ws_id = create_resp.json()["id"]

        # Attempt public delete
        del_resp = client.delete(f"/api/workspaces/{default_ws_id}")
        assert del_resp.status_code == 403
        assert del_resp.json()["detail"] == "Failed to delete workspace: Default Workspace cannot be deleted"

    def test_delete_default_workspace_internal_allowed(self, client):
        """Internal delete of Default Workspace should be allowed (no deps present)."""
        # Create Default Workspace
        create_resp = client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert create_resp.status_code == 201
        default_ws_id = create_resp.json()["id"]

        # Internal delete should succeed
        del_resp = client.delete(f"/api/internal/workspaces/{default_ws_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["message"] in {"Workspace deleted successfully", "Workspace permanently deleted"}

    def test_internal_purge_handles_dependents(self, client):
        """Internal purge should delete dependents and workspace without FK errors."""
        # Create workspace and a MAS dependent
        ws_resp = client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert ws_resp.status_code == 201
        ws_id = ws_resp.json()["id"]

        mas_data = {
            "name": "WS-Purge Test MAS",
            "description": "",
            "agents": {"a1": {"type": "t"}},
            "config": {},
        }
        mas_resp = client.post(f"/api/workspaces/{ws_id}/multi-agentic-systems", json=mas_data)
        assert mas_resp.status_code == 201

        # Internal purge should succeed and remove workspace and dependents
        del_resp = client.delete(f"/api/internal/workspaces/{ws_id}?_purge=true")
        assert del_resp.status_code == 200
        assert del_resp.json()["message"] == "Workspace permanently deleted"

    def test_workspace_isolation_admin_users(self, client, setup_test_environment):
        """Test that admin users can only see workspaces they are members of.

        Note: 'admin' is the default user role, not a super admin role. All users including
        those with 'admin' role should only see workspaces they created or are members of.
        """
        from server.common import encrypt_data, get_global_encryption_key

        # Create two additional admin users (admin is the default role)
        db = RelationalDB()
        session = db.session_factory()
        key = get_global_encryption_key()

        user1_id = str(uuid.uuid4())
        user1 = User(
            id=user1_id,
            username="user1",
            password=encrypt_data("password1", key),
            domain="test.local",
            role="admin",  # admin is the default role for all users
        )
        session.add(user1)

        user2_id = str(uuid.uuid4())
        user2 = User(
            id=user2_id,
            username="user2",
            password=encrypt_data("password2", key),
            domain="test.local",
            role="admin",  # admin is the default role for all users
        )
        session.add(user2)
        session.commit()

        # Create API keys for both users
        user1_api_key = f"ioc_user1_test_key_{str(uuid.uuid4())[:32]}"
        user1_key_hash = hashlib.sha256(user1_api_key.encode()).hexdigest()
        user1_api_key_obj = ApiKey(
            user_id=user1_id,
            key_hash=user1_key_hash,
            key_preview=f"{user1_api_key[:15]}...",
            name="User1 Test API Key",
        )
        session.add(user1_api_key_obj)

        user2_api_key = f"ioc_user2_test_key_{str(uuid.uuid4())[:32]}"
        user2_key_hash = hashlib.sha256(user2_api_key.encode()).hexdigest()
        user2_api_key_obj = ApiKey(
            user_id=user2_id,
            key_hash=user2_key_hash,
            key_preview=f"{user2_api_key[:15]}...",
            name="User2 Test API Key",
        )
        session.add(user2_api_key_obj)
        session.commit()

        # Create authenticated clients for each user
        user1_client = TestClient(app)
        user1_client.headers = {"X-API-Key": user1_api_key}

        user2_client = TestClient(app)
        user2_client.headers = {"X-API-Key": user2_api_key}

        # Dev-user (from fixture) creates a workspace
        dev_ws_resp = client.post("/api/workspaces", json={"name": "Dev User Workspace"})
        assert dev_ws_resp.status_code == 201
        dev_ws_id = dev_ws_resp.json()["id"]

        # User1 creates a workspace
        user1_ws_resp = user1_client.post("/api/workspaces", json={"name": "User1 Workspace"})
        assert user1_ws_resp.status_code == 201
        user1_ws_id = user1_ws_resp.json()["id"]

        # User2 creates a workspace
        user2_ws_resp = user2_client.post("/api/workspaces", json={"name": "User2 Workspace"})
        assert user2_ws_resp.status_code == 201
        user2_ws_id = user2_ws_resp.json()["id"]

        # Dev-user should only see their own workspace (not all 3)
        dev_list_resp = client.get("/api/workspaces")
        assert dev_list_resp.status_code == 200
        dev_workspaces = dev_list_resp.json()["workspaces"]
        assert len(dev_workspaces) == 1
        assert dev_workspaces[0]["id"] == dev_ws_id

        # User1 should only see their own workspace
        user1_list_resp = user1_client.get("/api/workspaces")
        assert user1_list_resp.status_code == 200
        user1_workspaces = user1_list_resp.json()["workspaces"]
        assert len(user1_workspaces) == 1
        assert user1_workspaces[0]["id"] == user1_ws_id

        # User2 should only see their own workspace
        user2_list_resp = user2_client.get("/api/workspaces")
        assert user2_list_resp.status_code == 200
        user2_workspaces = user2_list_resp.json()["workspaces"]
        assert len(user2_workspaces) == 1
        assert user2_workspaces[0]["id"] == user2_ws_id

        # User1 should be able to access their workspace
        user1_get_resp = user1_client.get(f"/api/workspaces/{user1_ws_id}")
        assert user1_get_resp.status_code == 200
        assert user1_get_resp.json()["id"] == user1_ws_id

        # User1 should NOT be able to access User2's workspace
        user1_get_user2_ws_resp = user1_client.get(f"/api/workspaces/{user2_ws_id}")
        assert user1_get_user2_ws_resp.status_code == 403
        assert "Access denied" in user1_get_user2_ws_resp.json()["detail"]

        # User1 should NOT be able to update User2's workspace
        user1_update_user2_ws_resp = user1_client.put(
            f"/api/workspaces/{user2_ws_id}", json={"name": "Hacked Name"}
        )
        assert user1_update_user2_ws_resp.status_code == 403

        # User1 should NOT be able to delete User2's workspace
        user1_delete_user2_ws_resp = user1_client.delete(f"/api/workspaces/{user2_ws_id}")
        assert user1_delete_user2_ws_resp.status_code == 403

        session.close()

    def test_workspace_isolation_with_admin_membership(self, client, setup_test_environment):
        """Test that users can access workspaces when added as workspace admins."""
        from server.common import encrypt_data, get_global_encryption_key

        # Create a user
        db = RelationalDB()
        session = db.session_factory()
        key = get_global_encryption_key()

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            username="member_user",
            password=encrypt_data("password", key),
            domain="test.local",
            role="admin",
        )
        session.add(user)
        session.commit()

        # Create API key for the user
        user_api_key = f"ioc_member_test_key_{str(uuid.uuid4())[:32]}"
        user_key_hash = hashlib.sha256(user_api_key.encode()).hexdigest()
        user_api_key_obj = ApiKey(
            user_id=user_id,
            key_hash=user_key_hash,
            key_preview=f"{user_api_key[:15]}...",
            name="Member User Test API Key",
        )
        session.add(user_api_key_obj)
        session.commit()

        # Dev-user creates a workspace
        dev_ws_resp = client.post("/api/workspaces", json={"name": "Shared Workspace"})
        assert dev_ws_resp.status_code == 201
        dev_ws_id = dev_ws_resp.json()["id"]

        # Initially, user should not see the dev-user's workspace
        user_client = TestClient(app)
        user_client.headers = {"X-API-Key": user_api_key}

        user_list_resp = user_client.get("/api/workspaces")
        assert user_list_resp.status_code == 200
        assert len(user_list_resp.json()["workspaces"]) == 0

        # Add user as a VIEWER member - they SHOULD see the workspace (viewers can list workspaces)
        viewer_member = WorkspaceMember(
            workspace_id=dev_ws_id,
            user_id=user_id,
            role="viewer",
            created_by="dev-user",
        )
        session.add(viewer_member)
        session.commit()

        user_list_resp = user_client.get("/api/workspaces")
        assert user_list_resp.status_code == 200
        user_workspaces = user_list_resp.json()["workspaces"]
        assert len(user_workspaces) == 1  # Viewer can see the workspace
        assert user_workspaces[0]["id"] == dev_ws_id

        # Viewer should be able to read the workspace details
        user_get_resp = user_client.get(f"/api/workspaces/{dev_ws_id}")
        assert user_get_resp.status_code == 200
        assert user_get_resp.json()["id"] == dev_ws_id

        # Viewer should NOT be able to update the workspace
        user_update_resp = user_client.put(
            f"/api/workspaces/{dev_ws_id}",
            json={"name": "Updated Name"}
        )
        assert user_update_resp.status_code == 403  # Forbidden for viewers

        # Update user to workspace ADMIN role - now they can also modify
        viewer_member.role = "admin"
        session.commit()

        # Admin should be able to update the workspace
        user_update_resp = user_client.put(
            f"/api/workspaces/{dev_ws_id}",
            json={"name": "Admin Updated Name"}
        )
        assert user_update_resp.status_code == 200
        assert user_update_resp.json()["name"] == "Admin Updated Name"

        session.close()

    def test_workspace_creator_always_has_access(self, client, setup_test_environment):
        """Test that workspace creators always have access, even if not in workspace_member table."""
        from server.common import encrypt_data, get_global_encryption_key

        # Create a user
        db = RelationalDB()
        session = db.session_factory()
        key = get_global_encryption_key()

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            username="creator_user",
            password=encrypt_data("password", key),
            domain="test.local",
            role="admin",
        )
        session.add(user)
        session.commit()

        # Create API key for the user
        user_api_key = f"ioc_creator_test_key_{str(uuid.uuid4())[:32]}"
        user_key_hash = hashlib.sha256(user_api_key.encode()).hexdigest()
        user_api_key_obj = ApiKey(
            user_id=user_id,
            key_hash=user_key_hash,
            key_preview=f"{user_api_key[:15]}...",
            name="Creator User Test API Key",
        )
        session.add(user_api_key_obj)
        session.commit()

        user_client = TestClient(app)
        user_client.headers = {"X-API-Key": user_api_key}

        # User creates a workspace (automatically added as workspace admin)
        user_ws_resp = user_client.post("/api/workspaces", json={"name": "Creator Workspace"})
        assert user_ws_resp.status_code == 201
        user_ws_id = user_ws_resp.json()["id"]

        # User should see their created workspace
        user_list_resp = user_client.get("/api/workspaces")
        assert user_list_resp.status_code == 200
        user_workspaces = user_list_resp.json()["workspaces"]
        assert len(user_workspaces) == 1
        assert user_workspaces[0]["id"] == user_ws_id

        # Even if we remove them from workspace_member, they should still see it (as creator)
        session.query(WorkspaceMember).filter(
            WorkspaceMember.workspace_id == user_ws_id, WorkspaceMember.user_id == user_id
        ).delete()
        session.commit()

        # User should STILL see the workspace because they're the creator
        user_list_resp = user_client.get("/api/workspaces")
        assert user_list_resp.status_code == 200
        user_workspaces = user_list_resp.json()["workspaces"]
        assert len(user_workspaces) == 1
        assert user_workspaces[0]["id"] == user_ws_id

        session.close()

    def test_super_admin_can_see_all_workspaces(self, setup_test_environment):
        """Test that super_admin role can see all workspaces (future feature)."""
        from server.common import encrypt_data, get_global_encryption_key

        db = RelationalDB()
        session = db.session_factory()
        key = get_global_encryption_key()

        # Create a super_admin user
        super_admin_id = str(uuid.uuid4())
        super_admin = User(
            id=super_admin_id,
            username="superadmin",
            password=encrypt_data("password", key),
            domain="test.local",
            role="super_admin",
        )
        session.add(super_admin)
        session.commit()

        # Create API key for super_admin
        super_admin_api_key = f"ioc_superadmin_key_{str(uuid.uuid4())[:32]}"
        super_admin_key_hash = hashlib.sha256(super_admin_api_key.encode()).hexdigest()
        super_admin_api_key_obj = ApiKey(
            user_id=super_admin_id,
            key_hash=super_admin_key_hash,
            key_preview=f"{super_admin_api_key[:15]}...",
            name="Super Admin Test API Key",
        )
        session.add(super_admin_api_key_obj)
        session.commit()

        # Create super_admin client
        super_admin_client = TestClient(app)
        super_admin_client.headers = {"X-API-Key": super_admin_api_key}

        # Create regular users
        user1_id = str(uuid.uuid4())
        user1 = User(
            id=user1_id,
            username="user1",
            password=encrypt_data("password1", key),
            domain="test.local",
            role="admin",
        )
        session.add(user1)

        user2_id = str(uuid.uuid4())
        user2 = User(
            id=user2_id,
            username="user2",
            password=encrypt_data("password2", key),
            domain="test.local",
            role="admin",
        )
        session.add(user2)
        session.commit()

        # Create API keys for regular users
        user1_api_key = f"ioc_user1_test_key_{str(uuid.uuid4())[:32]}"
        user1_key_hash = hashlib.sha256(user1_api_key.encode()).hexdigest()
        user1_api_key_obj = ApiKey(
            user_id=user1_id,
            key_hash=user1_key_hash,
            key_preview=f"{user1_api_key[:15]}...",
            name="User1 Test API Key",
        )
        session.add(user1_api_key_obj)

        user2_api_key = f"ioc_user2_test_key_{str(uuid.uuid4())[:32]}"
        user2_key_hash = hashlib.sha256(user2_api_key.encode()).hexdigest()
        user2_api_key_obj = ApiKey(
            user_id=user2_id,
            key_hash=user2_key_hash,
            key_preview=f"{user2_api_key[:15]}...",
            name="User2 Test API Key",
        )
        session.add(user2_api_key_obj)
        session.commit()

        # Create clients for regular users
        user1_client = TestClient(app)
        user1_client.headers = {"X-API-Key": user1_api_key}

        user2_client = TestClient(app)
        user2_client.headers = {"X-API-Key": user2_api_key}

        # User1 creates a workspace
        user1_ws_resp = user1_client.post("/api/workspaces", json={"name": "User1 Workspace"})
        assert user1_ws_resp.status_code == 201
        user1_ws_id = user1_ws_resp.json()["id"]

        # User2 creates a workspace
        user2_ws_resp = user2_client.post("/api/workspaces", json={"name": "User2 Workspace"})
        assert user2_ws_resp.status_code == 201
        user2_ws_id = user2_ws_resp.json()["id"]

        # Super admin should see all workspaces without being a member
        super_admin_list_resp = super_admin_client.get("/api/workspaces")
        assert super_admin_list_resp.status_code == 200
        super_admin_workspaces = super_admin_list_resp.json()["workspaces"]
        assert len(super_admin_workspaces) == 2

        super_admin_ws_ids = {ws["id"] for ws in super_admin_workspaces}
        assert user1_ws_id in super_admin_ws_ids
        assert user2_ws_id in super_admin_ws_ids

        # Super admin should be able to access any workspace
        super_admin_get_resp = super_admin_client.get(f"/api/workspaces/{user1_ws_id}")
        assert super_admin_get_resp.status_code == 200
        assert super_admin_get_resp.json()["id"] == user1_ws_id

        session.close()

    def test_multiple_users_can_create_workspaces_with_same_name(self, setup_test_environment):
        """Test that different users can create workspaces with the same name (e.g., 'Default Workspace')."""
        from server.common import encrypt_data, get_global_encryption_key

        db = RelationalDB()
        session = db.session_factory()
        key = get_global_encryption_key()

        # Create two different users
        user1_id = str(uuid.uuid4())
        user1 = User(
            id=user1_id,
            username="user_a",
            password=encrypt_data("password1", key),
            domain="test.local",
            role="admin",
        )
        session.add(user1)

        user2_id = str(uuid.uuid4())
        user2 = User(
            id=user2_id,
            username="user_b",
            password=encrypt_data("password2", key),
            domain="test.local",
            role="admin",
        )
        session.add(user2)
        session.commit()

        # Create API keys for both users
        user1_api_key = f"ioc_user1_key_{str(uuid.uuid4())[:32]}"
        user1_key_hash = hashlib.sha256(user1_api_key.encode()).hexdigest()
        user1_api_key_obj = ApiKey(
            user_id=user1_id,
            key_hash=user1_key_hash,
            key_preview=f"{user1_api_key[:15]}...",
            name="User A Test API Key",
        )
        session.add(user1_api_key_obj)

        user2_api_key = f"ioc_user2_key_{str(uuid.uuid4())[:32]}"
        user2_key_hash = hashlib.sha256(user2_api_key.encode()).hexdigest()
        user2_api_key_obj = ApiKey(
            user_id=user2_id,
            key_hash=user2_key_hash,
            key_preview=f"{user2_api_key[:15]}...",
            name="User B Test API Key",
        )
        session.add(user2_api_key_obj)
        session.commit()

        # Create clients for both users
        user1_client = TestClient(app)
        user1_client.headers = {"X-API-Key": user1_api_key}

        user2_client = TestClient(app)
        user2_client.headers = {"X-API-Key": user2_api_key}

        # User A creates a workspace named "Default Workspace"
        user1_ws_resp = user1_client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert user1_ws_resp.status_code == 201
        user1_ws_id = user1_ws_resp.json()["id"]

        # User B should also be able to create a workspace named "Default Workspace"
        user2_ws_resp = user2_client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert user2_ws_resp.status_code == 201
        user2_ws_id = user2_ws_resp.json()["id"]

        # The workspace IDs should be different
        assert user1_ws_id != user2_ws_id

        # Each user should only see their own workspace
        user1_list_resp = user1_client.get("/api/workspaces")
        assert user1_list_resp.status_code == 200
        user1_workspaces = user1_list_resp.json()["workspaces"]
        assert len(user1_workspaces) == 1
        assert user1_workspaces[0]["id"] == user1_ws_id
        assert user1_workspaces[0]["name"] == "Default Workspace"

        user2_list_resp = user2_client.get("/api/workspaces")
        assert user2_list_resp.status_code == 200
        user2_workspaces = user2_list_resp.json()["workspaces"]
        assert len(user2_workspaces) == 1
        assert user2_workspaces[0]["id"] == user2_ws_id
        assert user2_workspaces[0]["name"] == "Default Workspace"

        session.close()
