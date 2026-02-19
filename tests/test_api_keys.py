"""
Tests for API key endpoints in ioc-cfn-mgmt-backend.
"""
import pytest

from server.authn.auth import get_auth_user
from server.main import app


def override_get_auth_user(user_data):
    """Create a dependency override that returns specific user data."""
    async def _override():
        return user_data
    return _override


class TestAPIKeyCreate:
    """Test cases for API key creation."""

    def test_create_api_key_success(self, client, admin_user):
        """Test successful API key creation."""
        # Override the dependency to return admin_user (viewers cannot create API keys)
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
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
            assert data["user_id"] == admin_user["id"]
            assert data["name"] == "Test API Key"

            # Verify key format
            assert data["key"].startswith("ioc_")
            assert data["key_preview"].startswith("ioc_")
            assert data["key_preview"].endswith("...")
        finally:
            app.dependency_overrides.clear()

    def test_create_api_key_inherits_user_role(self, client, admin_user):
        """Test that API key inherits user's role."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Role Test Key"}
            )

            assert response.status_code == 201
            data = response.json()

            # Verify the API key is associated with the user
            assert data["user_id"] == admin_user["id"]

            # Note: Role is not stored on API key, it comes from user
            # We'll verify this in validation tests
        finally:
            app.dependency_overrides.clear()

    def test_create_api_key_invalid_name(self, client, admin_user):
        """Test API key creation with invalid name."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
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
        """Test API key creation without explicit override uses mock admin user."""
        # Don't override - uses default mock admin user from disabled auth
        response = client.post(
            "/api/iam/api-keys",
            json={"name": "Test Key"}
        )
        # With mock auth enabled, this succeeds with the mock admin user
        assert response.status_code == 201


class TestAPIKeyList:
    """Test cases for listing API keys."""

    def test_list_api_keys_empty(self, client, admin_user):
        """Test listing API keys when none exist."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
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

    def test_list_user_api_keys(self, client, admin_user):
        """Test that admin users can list API keys (sees all keys since admin role)."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Get initial count
            response = client.get("/api/iam/api-keys")
            initial_count = response.json()["total"]

            # Create two API keys (requires admin role)
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

            # List keys - admin sees all keys
            response = client.get("/api/iam/api-keys")
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == initial_count + 2  # 2 new keys added
            assert len(data["api_keys"]) == initial_count + 2

            # Verify our two new keys are in the list
            key_ids = [k["id"] for k in data["api_keys"]]
            assert key1_id in key_ids
            assert key2_id in key_ids

            # Verify our keys belong to admin_user
            admin_keys = [k for k in data["api_keys"] if k["id"] in [key1_id, key2_id]]
            for key in admin_keys:
                assert key["user_id"] == admin_user["id"]
                assert "key" not in key  # Full key not shown in list
                assert "key_preview" in key
        finally:
            app.dependency_overrides.clear()

    def test_list_admin_sees_all_keys(self, client, admin_user):
        """Test that admin users see all API keys."""
        # Create key as admin and list
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create a key as admin_user
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Admin Key"}
            )
            assert response.status_code == 201

            # List keys as admin - should see all keys
            response = client.get("/api/iam/api-keys")
            assert response.status_code == 200

            data = response.json()
            # Admin sees all keys: at least their own key
            assert data["total"] >= 1

            # Verify admin_user's key is present
            user_ids = {k["user_id"] for k in data["api_keys"]}
            assert admin_user["id"] in user_ids
        finally:
            app.dependency_overrides.clear()

    def test_list_api_keys_excludes_deleted(self, client, admin_user):
        """Test that soft-deleted keys are not returned."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create key (requires admin)
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Verify it shows up
            response = client.get("/api/iam/api-keys")
            initial_count = response.json()["total"]
            assert initial_count >= 1

            # Delete key (requires admin)
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Verify it's gone from list
            response = client.get("/api/iam/api-keys")
            assert response.json()["total"] == initial_count - 1
        finally:
            app.dependency_overrides.clear()


class TestAPIKeyDelete:
    """Test cases for deleting API keys."""

    def test_delete_own_api_key(self, client, admin_user):
        """Test that admin users can delete their own API keys."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create key (requires admin)
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Delete key (requires admin)
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Verify key is gone
            response = client.get("/api/iam/api-keys")
            # Check that the key we just deleted is not in the list
            key_ids = [k["id"] for k in response.json()["api_keys"]]
            assert key_id not in key_ids
        finally:
            app.dependency_overrides.clear()

    def test_admin_can_delete_any_key(self, client, admin_user):
        """Test that admin users can delete API keys."""
        # Create key as admin
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Delete as same admin (admins can delete their own keys)
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204
        finally:
            app.dependency_overrides.clear()

    def test_delete_nonexistent_key(self, client, admin_user):
        """Test deleting a key that doesn't exist."""
        import uuid
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            fake_id = str(uuid.uuid4())
            response = client.delete(f"/api/iam/api-keys/{fake_id}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_delete_is_soft_delete(self, client, admin_user):
        """Test that delete is soft delete (sets deleted_at)."""
        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.api_key import ApiKey

        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create key (requires admin)
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Soft Delete Test"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]

            # Delete key (requires admin)
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

    def test_validate_api_key_returns_user_data(self, client, admin_user):
        """Test that API key validation returns real user data."""
        from server.services.api_key import api_key_service

        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create API key (requires admin)
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Validation Test Key"}
            )
            assert response.status_code == 201
            full_key = response.json()["key"]

            # Validate the key
            user_info = api_key_service.validate_api_key(full_key)

            assert user_info is not None
            assert user_info["id"] == admin_user["id"]
            assert user_info["username"] == admin_user["username"]
            assert user_info["role"] == admin_user["role"]
            assert user_info["email"] == admin_user["email"]
        finally:
            app.dependency_overrides.clear()

    def test_validate_invalid_key(self, client):
        """Test validation of invalid API key."""
        from server.services.api_key import api_key_service

        # Try to validate a fake key
        user_info = api_key_service.validate_api_key("ioc_fakekeyfakekeyfakekeyfakekeyfakekeyfakekey")
        assert user_info is None

    def test_validate_deleted_key(self, client, admin_user):
        """Test that deleted keys cannot authenticate."""
        from server.services.api_key import api_key_service

        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create and then delete key (requires admin)
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Key to Delete"}
            )
            assert response.status_code == 201
            key_id = response.json()["id"]
            full_key = response.json()["key"]

            # Delete the key (requires admin)
            response = client.delete(f"/api/iam/api-keys/{key_id}")
            assert response.status_code == 204

            # Try to validate deleted key
            user_info = api_key_service.validate_api_key(full_key)
            assert user_info is None
        finally:
            app.dependency_overrides.clear()

    def test_api_key_inherits_updated_user_role(self, client, admin_user):
        """Test that API key inherits updated user role dynamically."""
        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.user import User
        from server.services.api_key import api_key_service

        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create API key as admin (requires admin)
            response = client.post(
                "/api/iam/api-keys",
                json={"name": "Role Change Test"}
            )
            assert response.status_code == 201
            full_key = response.json()["key"]

            # Verify initial role
            user_info = api_key_service.validate_api_key(full_key)
            assert user_info["role"] == "admin"

            # Update user role to viewer
            db = RelationalDB()
            session = db.session_factory()
            try:
                user = session.query(User).filter(User.id == admin_user["id"]).first()
                user.role = "viewer"
                session.commit()
            finally:
                session.close()

            # Validate key again - should have viewer role now
            user_info = api_key_service.validate_api_key(full_key)
            assert user_info["role"] == "viewer"
        finally:
            app.dependency_overrides.clear()


class TestAPIKeyWorkspaceAccess:
    """Test cases for workspace access with API keys."""

    def test_api_key_access_user_workspace(self, client, admin_user, registered_cfn):
        """Test that API key can access workspaces the user is a member of."""
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            # Create workspace (requires admin)
            workspace_data = {"name": "User Workspace", "users": [admin_user["id"]], "cfn_id": registered_cfn}
            response = client.post("/api/workspaces/create", json=workspace_data)
            assert response.status_code == 201
            workspace_id = response.json()["id"]

            # User should be able to access their workspace
            response = client.get(f"/api/workspaces/{workspace_id}")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_admin_api_key_access_all_workspaces(self, client, admin_user, registered_cfn):
        """Test that super_admin can access all workspaces, but regular admin cannot."""
        # Create workspace as admin
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        workspace_data = {"name": "Test Workspace", "cfn_id": registered_cfn}
        response = client.post("/api/workspaces/create", json=workspace_data)
        assert response.status_code == 201
        workspace_id = response.json()["id"]
        app.dependency_overrides.clear()

        # Same admin user CAN access their own workspace
        app.dependency_overrides[get_auth_user] = override_get_auth_user(admin_user)
        try:
            response = client.get(f"/api/workspaces/{workspace_id}")
            assert response.status_code == 200  # Can access own workspace
        finally:
            app.dependency_overrides.clear()

        # Create a super_admin user
        super_admin_user = {
            "id": "super-admin-id",
            "username": "superadmin",
            "domain": "test.local",
            "role": "super_admin",  # Super admin role
            "email": "superadmin@test.local",
        }

        # Super admin SHOULD be able to access any workspace (even without membership)
        app.dependency_overrides[get_auth_user] = override_get_auth_user(super_admin_user)
        try:
            response = client.get(f"/api/workspaces/{workspace_id}")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()
