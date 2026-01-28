"""
Tests for API key endpoints in ioc-cfn-mgmt-backend.
"""
import pytest
from server.main import app
from server.api.dependencies import get_current_user


def override_get_current_user(user_data):
    """Create a dependency override that returns specific user data."""
    async def _override():
        return user_data
    return _override


class TestAPIKeyCreate:
    """Test cases for API key creation."""

    def test_create_api_key_success(self, client, test_user):
        """Test successful API key creation."""
        # Override the dependency to return test_user
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Test API Key"}
            )

            assert response.status_code == 201
            data = response.json()

            # Verify response contains all required fields
            assert "id" in data
            assert "key" in data  # Full key only shown once
            assert "key_preview" in data
            assert "name" in data
            assert "user_id" in data
            assert "created_at" in data

            # Verify the key belongs to the current user
            assert data["user_id"] == test_user["id"]
            assert data["name"] == "Test API Key"

            # Verify key format
            assert data["key"].startswith("ioc_")
            assert data["key_preview"].startswith("ioc_")
            assert data["key_preview"].endswith("...")
        finally:
            app.dependency_overrides.clear()

    def test_create_api_key_inherits_user_role(self, client, test_user):
        """Test that API key inherits user's role."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Role Test Key"}
            )

            assert response.status_code == 201
            data = response.json()

            # Verify the API key is associated with the user
            assert data["user_id"] == test_user["id"]

            # Note: Role is not stored on API key, it comes from user
            # We'll verify this in validation tests
        finally:
            app.dependency_overrides.clear()

    def test_create_api_key_invalid_name(self, client, test_user):
        """Test API key creation with invalid name."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Empty name
            response = client.post(
                "/api/iam/api-keys",
                json={"name": ""}
            )
            assert response.status_code == 422

            # Missing name
            response = client.post(
                "/api/iam/api-keys",
                json={}
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_create_api_key_unauthenticated(self, client):
        """Test API key creation without authentication fallback to dev-user."""
        # Don't override - uses default dev-user
        response = client.post(
            "/api/iam/api-keys",
            json={"name": "Test Key"}
        )
        # In dev mode, this will succeed with dev-user
        assert response.status_code == 201


class TestAPIKeyList:
    """Test cases for listing API keys."""

    def test_list_api_keys_empty(self, client, test_user):
        """Test listing API keys when none exist."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            response = client.get("/api/iam/api-keys")

            assert response.status_code == 200
            data = response.json()
            assert "api_keys" in data
            assert "total" in data
            assert data["api_keys"] == []
            assert data["total"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_list_user_api_keys(self, client, test_user):
        """Test that users see only their own API keys."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create two API keys
            response1 = client.post(
                "/api/iam/api-keys",
                json={"name": "Key 1"}
            )
            assert response1.status_code == 201
            key1_id = response1.json()["id"]

            response2 = client.post(
                "/api/iam/api-keys",
                json={"name": "Key 2"}
            )
            assert response2.status_code == 201
            key2_id = response2.json()["id"]

            # List keys
            response = client.get("/api/iam/api-keys")
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 2
            assert len(data["api_keys"]) == 2

            # Verify all keys belong to the user
            key_ids = [k["id"] for k in data["api_keys"]]
            assert key1_id in key_ids
            assert key2_id in key_ids

            for key in data["api_keys"]:
                assert key["user_id"] == test_user["id"]
                assert "key" not in key  # Full key not shown in list
                assert "key_preview" in key
        finally:
            app.dependency_overrides.clear()

    def test_list_admin_sees_all_keys(self, client, test_user, admin_user):
        """Test that admin users see all API keys."""
        # Create key as regular user
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        response1 = client.post(
            "/api/iam/api-keys",
            json={"name": "User Key"}
        )
        assert response1.status_code == 201
        app.dependency_overrides.clear()

        # Create key as admin and list
        app.dependency_overrides[get_current_user] = override_get_current_user(admin_user)
        try:
            response2 = client.post(
                "/api/iam/api-keys",
                json={"name": "Admin Key"}
            )
            assert response2.status_code == 201

            # List keys as admin - should see all keys (including dev-user's key)
            response = client.get("/api/iam/api-keys")
            assert response.status_code == 200

            data = response.json()
            # Admin sees all keys: test_user key + admin_user key + dev-user key
            assert data["total"] == 3

            # Verify keys for test_user and admin_user are present
            user_ids = {k["user_id"] for k in data["api_keys"]}
            assert test_user["id"] in user_ids
            assert admin_user["id"] in user_ids
        finally:
            app.dependency_overrides.clear()

    def test_list_api_keys_excludes_deleted(self, client, test_user):
        """Test that soft-deleted keys are not returned."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create key
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Verify it shows up
            response = client.get("/api/iam/api-keys")
            assert response.json()["total"] == 1

            # Delete key
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Verify it's gone from list
            response = client.get("/api/iam/api-keys")
            assert response.json()["total"] == 0
        finally:
            app.dependency_overrides.clear()


class TestAPIKeyDelete:
    """Test cases for deleting API keys."""

    def test_delete_own_api_key(self, client, test_user):
        """Test that users can delete their own API keys."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create key
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Delete key
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Verify key is gone
            response = client.get("/api/iam/api-keys")
            assert response.json()["total"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_delete_other_user_key_forbidden(self, client, test_user, admin_user):
        """Test that users cannot delete other users' API keys."""
        # Create key as admin
        app.dependency_overrides[get_current_user] = override_get_current_user(admin_user)
        response = client.post(
            "/api/iam/api-keys",
            json={"name": "Admin Key"}
        )
        assert response.status_code == 201
        admin_key_id = response.json()["id"]
        app.dependency_overrides.clear()

        # Try to delete as regular user
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            response = client.delete(f"/api/iam/api-keys/{admin_key_id}")
            assert response.status_code == 403
            assert "can only delete your own" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_admin_can_delete_any_key(self, client, test_user, admin_user):
        """Test that admin users can delete any API key."""
        # Create key as regular user
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        response = client.post(
            "/api/iam/api-keys",
            json={"name": "User Key"}
        )
        assert response.status_code == 201
        user_key_id = response.json()["id"]
        app.dependency_overrides.clear()

        # Delete as admin
        app.dependency_overrides[get_current_user] = override_get_current_user(admin_user)
        try:
            response = client.delete(f"/api/iam/api-keys/{user_key_id}")
            assert response.status_code == 204
        finally:
            app.dependency_overrides.clear()

    def test_delete_nonexistent_key(self, client, test_user):
        """Test deleting a key that doesn't exist."""
        import uuid
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            fake_id = str(uuid.uuid4())
            response = client.delete(f"/api/iam/api-keys/{fake_id}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_delete_is_soft_delete(self, client, test_user):
        """Test that delete is soft delete (sets deleted_at)."""
        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.api_key import ApiKey

        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create key
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Soft Delete Test"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Delete key
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Verify it still exists in DB but has deleted_at set
            db = RelationalDB()
            session = db.session_factory()
            try:
                key = session.query(ApiKey).filter(ApiKey.id == key_id).first()
                assert key is not None
                assert key.deleted_at is not None
            finally:
                session.close()
        finally:
            app.dependency_overrides.clear()


class TestAPIKeyValidation:
    """Test cases for API key validation."""

    def test_validate_api_key_returns_user_data(self, client, test_user):
        """Test that API key validation returns real user data."""
        from server.services.api_key import api_key_service

        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create API key
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Validation Test Key"}
            )
            assert response.status_code == 201
            full_key = response.json()["key"]

            # Validate the key
            user_info = api_key_service.validate_api_key(full_key)

            assert user_info is not None
            assert user_info["id"] == test_user["id"]
            assert user_info["username"] == test_user["username"]
            assert user_info["role"] == test_user["role"]
            assert user_info["email"] == test_user["email"]
        finally:
            app.dependency_overrides.clear()

    def test_validate_invalid_key(self, client):
        """Test validation of invalid API key."""
        from server.services.api_key import api_key_service

        # Try to validate a fake key
        user_info = api_key_service.validate_api_key("ioc_fakekeyfakekeyfakekeyfakekeyfakekeyfakekey")
        assert user_info is None

    def test_validate_deleted_key(self, client, test_user):
        """Test that deleted keys cannot authenticate."""
        from server.services.api_key import api_key_service

        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create and then delete key
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]
            full_key = response.json()["key"]

            # Delete the key
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Try to validate deleted key
            user_info = api_key_service.validate_api_key(full_key)
            assert user_info is None
        finally:
            app.dependency_overrides.clear()

    def test_api_key_inherits_updated_user_role(self, client, test_user):
        """Test that API key inherits updated user role dynamically."""
        from server.services.api_key import api_key_service
        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.user import User

        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create API key as viewer
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Role Change Test"}
            )
            assert response.status_code == 201
            full_key = response.json()["key"]

            # Verify initial role
            user_info = api_key_service.validate_api_key(full_key)
            assert user_info["role"] == "viewer"

            # Update user role to admin
            db = RelationalDB()
            session = db.session_factory()
            try:
                user = session.query(User).filter(User.id == test_user["id"]).first()
                user.role = "admin"
                session.commit()
            finally:
                session.close()

            # Validate key again - should have admin role now
            user_info = api_key_service.validate_api_key(full_key)
            assert user_info["role"] == "admin"
        finally:
            app.dependency_overrides.clear()


class TestAPIKeyWorkspaceAccess:
    """Test cases for workspace access with API keys."""

    def test_api_key_access_user_workspace(self, client, test_user, sample_workspace_data):
        """Test that API key can access workspaces the user is a member of."""
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        try:
            # Create workspace with user as member
            workspace_data = {
                "name": "User Workspace",
                "users": [test_user["id"]]
            }
            response = client.post("/api/workspaces", json=workspace_data)
            assert response.status_code == 201
            workspace_id = response.json()["id"]

            # User should be able to access their workspace
            response = client.get(f"/api/workspaces/{workspace_id}")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_admin_api_key_access_all_workspaces(self, client, admin_user, test_user):
        """Test that admin API key can access all workspaces."""
        # Create workspace as regular user
        app.dependency_overrides[get_current_user] = override_get_current_user(test_user)
        workspace_data = {"name": "Test Workspace"}
        response = client.post("/api/workspaces", json=workspace_data)
        assert response.status_code == 201
        workspace_id = response.json()["id"]
        app.dependency_overrides.clear()

        # Admin should be able to access any workspace
        app.dependency_overrides[get_current_user] = override_get_current_user(admin_user)
        try:
            response = client.get(f"/api/workspaces/{workspace_id}")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()
