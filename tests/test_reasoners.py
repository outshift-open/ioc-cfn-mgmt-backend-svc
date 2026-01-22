"""
Tests for Reasoner endpoints in ioc-cfn-mgmt-backend.
"""
import pytest


class TestReasonerEndpoints:
    """Test cases for Reasoner management endpoints."""

    @pytest.fixture
    def created_mas(self, client, created_workspace):
        """Create a MAS and return its ID."""
        mas_data = {
            "name": "Test MAS for Reasoner",
            "description": "MAS for reasoner testing",
            "agents": {"agent1": {"type": "test"}},
            "config": {},
        }
        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert response.status_code == 201
        return response.json()["id"]

    def test_create_reasoner_success(self, client, created_workspace, created_mas):
        """Test successful reasoner creation."""
        reasoner_data = {"name": "Test Reasoner", "mas_id": created_mas, "config": {"reasoning_type": "logical"}}

        response = client.post(f"/api/workspaces/{created_workspace}/reasoners", json=reasoner_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Reasoner"
        assert isinstance(data["id"], str)

        import uuid

        uuid.UUID(data["id"])

    def test_create_reasoner_workspace_not_found(self, client, created_mas):
        """Test creating reasoner in non-existent workspace."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"
        reasoner_data = {"name": "Test Reasoner", "mas_id": created_mas, "description": "A test reasoner", "config": {}}

        response = client.post(f"/api/workspaces/{fake_workspace_id}/reasoners", json=reasoner_data)

        assert response.status_code == 404

    def test_create_reasoner_invalid_mas_id(self, client, created_workspace):
        """Test creating reasoner with non-existent MAS ID."""
        fake_mas_id = "00000000-0000-0000-0000-000000000000"
        reasoner_data = {"name": "Test Reasoner", "mas_id": fake_mas_id, "config": {}}

        response = client.post(f"/api/workspaces/{created_workspace}/reasoners", json=reasoner_data)

        assert response.status_code == 404

    def test_create_reasoner_missing_required_fields(self, client, created_workspace):
        """Test creating reasoner with missing required fields."""
        reasoner_data = {"config": {"test": "Missing name and mas_id fields"}}

        response = client.post(f"/api/workspaces/{created_workspace}/reasoners", json=reasoner_data)

        assert response.status_code == 422

    def test_create_reasoner_invalid_workspace_id(self, client, created_mas):
        """Test creating reasoner with invalid workspace ID format."""
        reasoner_data = {"name": "Test Reasoner", "mas_id": created_mas, "description": "A test reasoner", "config": {}}

        response = client.post("/api/workspaces/invalid-id/reasoners", json=reasoner_data)

        assert response.status_code == 404

    def test_list_reasoners_empty(self, client, created_workspace):
        """Test listing reasoners when none exist."""
        response = client.get(f"/api/workspaces/{created_workspace}/reasoners")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data["reasoners"]) == 0

    def test_list_reasoners_with_data(self, client, created_workspace, created_mas):
        """Test listing reasoners with existing data."""
        # Create a reasoner first
        reasoner_data = {"name": "Test Reasoner 1", "mas_id": created_mas, "config": {"reasoning_type": "logical"}}

        create_response = client.post(f"/api/workspaces/{created_workspace}/reasoners", json=reasoner_data)
        assert create_response.status_code == 201

        # List reasoners
        response = client.get(f"/api/workspaces/{created_workspace}/reasoners")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data["reasoners"]) == 1

        reasoner = data["reasoners"][0]
        assert reasoner["name"] == "Test Reasoner 1"
        assert reasoner["mas_id"] == created_mas
        assert reasoner["config"] == {"reasoning_type": "logical"}
        assert "id" in reasoner
        assert "created_at" in reasoner
        assert "updated_at" in reasoner

    def test_list_reasoners_workspace_not_found(self, client):
        """Test listing reasoners in non-existent workspace."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"

        response = client.get(f"/api/workspaces/{fake_workspace_id}/reasoners")

        assert response.status_code == 404

    def test_create_reasoner_with_empty_config(self, client, created_workspace, created_mas):
        """Test creating reasoner with empty config."""
        reasoner_data = {"name": "Test Reasoner Empty Config", "mas_id": created_mas, "config": {}}

        response = client.post(f"/api/workspaces/{created_workspace}/reasoners", json=reasoner_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Reasoner Empty Config"
