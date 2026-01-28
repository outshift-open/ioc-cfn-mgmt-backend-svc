"""
Tests for JWT authentication endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from server.main import app


@pytest.fixture
def unauthenticated_client(setup_test_environment):
    """Create a test client without authentication headers."""
    return TestClient(app)


class TestJWTAuthentication:
    """Test cases for JWT-based authentication."""

    def test_login_with_valid_credentials(self, unauthenticated_client):
        """Test login with valid username and password returns JWT tokens."""
        # Login without API key (public endpoint)
        client_no_auth = unauthenticated_client

        response = client_no_auth.post("/api/auth/login", json={
            "username": "dev-user",
            "password": "dev"
        })

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["username"] == "dev-user"
        assert data["user"]["role"] == "admin"

    def test_login_with_invalid_credentials(self, unauthenticated_client):
        """Test login with invalid credentials returns 401."""
        client_no_auth = unauthenticated_client

        response = client_no_auth.post("/api/auth/login", json={
            "username": "dev-user",
            "password": "wrongpassword"
        })

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_with_nonexistent_user(self, unauthenticated_client):
        """Test login with nonexistent user returns 401."""
        client_no_auth = unauthenticated_client

        response = client_no_auth.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "password"
        })

        assert response.status_code == 401

    def test_api_access_with_jwt_token(self, unauthenticated_client):
        """Test that JWT token can be used to access protected endpoints."""
        # Login first
        login_response = unauthenticated_client.post("/api/auth/login", json={
            "username": "dev-user",
            "password": "dev"
        })

        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Use JWT token to access workspaces endpoint
        response = unauthenticated_client.get("/api/workspaces/", headers={
            "Authorization": f"Bearer {token}"
        })

        assert response.status_code == 200
        assert "workspaces" in response.json()

    def test_api_access_with_api_key_still_works(self, client):
        """Test that API key authentication still works alongside JWT."""
        # This client has API key in headers from fixture
        response = client.get("/api/workspaces/")

        assert response.status_code == 200
        assert "workspaces" in response.json()

    def test_api_access_without_auth_fails(self, unauthenticated_client):
        """Test that accessing protected endpoint without auth fails."""
        response = unauthenticated_client.get("/api/workspaces/")

        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    def test_refresh_token_generates_new_access_token(self, unauthenticated_client):
        """Test that refresh token can be used to get a new access token."""
        # Login first
        login_response = unauthenticated_client.post("/api/auth/login", json={
            "username": "dev-user",
            "password": "dev"
        })

        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token to get new access token
        refresh_response = unauthenticated_client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })

        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify new access token works
        new_token = data["access_token"]
        response = unauthenticated_client.get("/api/workspaces/", headers={
            "Authorization": f"Bearer {new_token}"
        })

        assert response.status_code == 200

    def test_invalid_refresh_token_fails(self, unauthenticated_client):
        """Test that invalid refresh token is rejected."""
        response = unauthenticated_client.post("/api/auth/refresh", json={
            "refresh_token": "invalid_token_12345"
        })

        assert response.status_code == 401
