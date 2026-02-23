"""
Tests for Multi-Agent System endpoints in ioc-cfn-mgmt-plane.
"""
import pytest


class TestMASEndpoints:
    """Test cases for Multi-Agent System management endpoints."""

    def test_create_mas_success(self, client, created_workspace):
        """Test successful MAS creation."""
        mas_data = {
            "name": "Test MAS",
            "description": "A test multi-agent system",
            "agents": {"agent1": {"type": "reasoning"}, "agent2": {"type": "planning"}},
            "config": {"param1": "value1"},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test MAS"
        assert isinstance(data["id"], str)

        import uuid

        uuid.UUID(data["id"])

    def test_create_mas_workspace_not_found(self, client):
        """Test creating MAS in non-existent workspace."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"
        mas_data = {
            "name": "Test MAS - Workspace Not Found",
            "description": "A test multi-agent system",
            "agents": {"agent1": {"type": "reasoning"}},
            "config": {},
        }

        response = client.post(f"/api/workspaces/{fake_workspace_id}/multi-agentic-systems", json=mas_data)

        assert response.status_code == 404

    def test_create_mas_invalid_workspace_id(self, client):
        """Test creating MAS with invalid workspace ID format."""
        mas_data = {
            "name": "Test MAS - Invalid Workspace ID",
            "description": "A test multi-agent system",
            "agents": {"agent1": {"type": "reasoning"}},
            "config": {},
        }

        response = client.post(f"/api/workspaces/invalid-id/multi-agentic-systems", json=mas_data)

        assert response.status_code == 404

    def test_create_mas_missing_required_fields(self, client, created_workspace):
        """Test creating MAS with missing required fields."""
        mas_data = {"description": "Missing name field"}

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        assert response.status_code == 422

    def test_list_mas_empty(self, client, created_workspace):
        """Test listing MAS when none exist."""
        response = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems")

        assert response.status_code == 200
        data = response.json()
        assert "systems" in data
        assert isinstance(data["systems"], list)
        assert len(data["systems"]) == 0

    def test_list_mas_with_data(self, client, created_workspace):
        """Test listing MAS with existing data."""
        # Create a MAS first
        mas_data = {
            "name": "Test MAS 1",
            "description": "First test MAS",
            "agents": {"agent1": {"type": "reasoning"}},
            "config": {"param1": "value1"},
        }

        create_response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert create_response.status_code == 201

        # List MAS
        response = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems")

        assert response.status_code == 200
        data = response.json()
        assert "systems" in data
        assert isinstance(data["systems"], list)
        assert len(data["systems"]) == 1

        mas = data["systems"][0]
        assert mas["name"] == "Test MAS 1"
        assert "id" in mas
        assert "workspace_id" in mas
        assert mas["description"] == "First test MAS"
        assert mas["agents"] == {"agent1": {"type": "reasoning"}}
        assert mas["config"] == {"param1": "value1"}
        assert "created_at" in mas
        assert "updated_at" in mas

    def test_list_mas_workspace_not_found(self, client):
        """Test listing MAS in non-existent workspace."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"

        response = client.get(f"/api/workspaces/{fake_workspace_id}/multi-agentic-systems")

        assert response.status_code == 404

    def test_create_mas_with_empty_agents(self, client, created_workspace):
        """Test creating MAS with empty agents list."""
        mas_data = {"name": "Test MAS", "description": "A test multi-agent system", "agents": {}, "config": {}}

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test MAS"
