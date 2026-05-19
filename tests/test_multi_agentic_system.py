# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

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
            "agents": [
                {"agent_id": "agent1", "config": {"type": "reasoning"}},
                {"agent_id": "agent2", "config": {"type": "planning"}},
            ],
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
            "agents": [{"agent_id": "agent1", "config": {"type": "reasoning"}}],
            "config": {},
        }

        response = client.post(f"/api/workspaces/{fake_workspace_id}/multi-agentic-systems", json=mas_data)

        assert response.status_code == 404

    def test_create_mas_invalid_workspace_id(self, client):
        """Test creating MAS with invalid workspace ID format."""
        mas_data = {
            "name": "Test MAS - Invalid Workspace ID",
            "description": "A test multi-agent system",
            "agents": [{"agent_id": "agent1", "config": {"type": "reasoning"}}],
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
            "agents": [{"agent_id": "agent1", "config": {"type": "reasoning"}}],
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
        assert mas["agents"][0]["agent_id"] == "agent1"
        assert mas["agents"][0]["config"] == {"type": "reasoning"}
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
        mas_data = {"name": "Test MAS", "description": "A test multi-agent system", "agents": [], "config": {}}

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test MAS"

    def test_create_mas_with_agent_identity_fields(self, client, created_workspace):
        """Test creating MAS with agents that include name, url, and identity."""
        mas_data = {
            "name": "Identity MAS",
            "description": "MAS with identity-enabled agents",
            "agents": [
                {
                    "agent_id": "retrieval-agent-1",
                    "name": "Retrieval Agent",
                    "url": "http://retrieval-agent:8080",
                    "identity": {
                        "type": "openclaw",
                        "identifiers": {"url": "main::agents::retrieval-agent-1"},
                    },
                },
                {
                    "agent_id": "planner-agent-1",
                    "name": "Planner Agent",
                    "url": "http://planner-agent:8081",
                    "identity": {
                        "type": "claude_code",
                        "identifiers": {"org_id": "23", "project_id": "79"},
                    },
                },
            ],
        }

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert response.status_code == 201
        mas_id = response.json()["id"]

        # GET the MAS and verify agent fields round-trip correctly
        get_response = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")
        assert get_response.status_code == 200
        data = get_response.json()

        agents = data["agents"]
        assert len(agents) == 2

        agent1 = agents[0]
        assert agent1["agent_id"] == "retrieval-agent-1"
        assert agent1["name"] == "Retrieval Agent"
        assert agent1["url"] == "http://retrieval-agent:8080"
        assert agent1["identity"]["type"] == "openclaw"
        assert agent1["identity"]["identifiers"] == {"url": "main::agents::retrieval-agent-1"}

        agent2 = agents[1]
        assert agent2["agent_id"] == "planner-agent-1"
        assert agent2["name"] == "Planner Agent"
        assert agent2["url"] == "http://planner-agent:8081"
        assert agent2["identity"]["type"] == "claude_code"
        assert agent2["identity"]["identifiers"] == {"org_id": "23", "project_id": "79"}

    def test_create_mas_agents_without_identity_returns_null(self, client, created_workspace):
        """Test that agents created without new fields return null for name, url, identity."""
        mas_data = {
            "name": "Legacy MAS",
            "agents": [
                {"agent_id": "agent-1", "config": {"type": "reasoning"}},
            ],
        }

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert response.status_code == 201
        mas_id = response.json()["id"]

        get_response = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")
        assert get_response.status_code == 200
        agent = get_response.json()["agents"][0]

        assert agent["agent_id"] == "agent-1"
        assert agent["name"] is None
        assert agent["url"] is None
        assert agent["identity"] is None
        assert agent["config"] == {"type": "reasoning"}

    def test_create_mas_mixed_agents_with_and_without_identity(self, client, created_workspace):
        """Test MAS with a mix of identity-enabled and legacy agents."""
        mas_data = {
            "name": "Mixed MAS",
            "agents": [
                {
                    "agent_id": "agent-with-identity",
                    "name": "OpenClaw Agent",
                    "url": "http://openclaw-agent:8080",
                    "identity": {
                        "type": "openclaw",
                        "identifiers": {"url": "main::agents::openclaw-1"},
                    },
                },
                {
                    "agent_id": "agent-without-identity",
                },
            ],
        }

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert response.status_code == 201
        mas_id = response.json()["id"]

        get_response = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")
        assert get_response.status_code == 200
        agents = get_response.json()["agents"]

        assert agents[0]["identity"]["type"] == "openclaw"
        assert agents[0]["name"] == "OpenClaw Agent"
        assert agents[1]["identity"] is None
        assert agents[1]["name"] is None

    def test_update_mas_add_identity_to_agent(self, client, created_workspace):
        """Test updating a MAS to add identity to an existing agent via PUT."""
        mas_data = {
            "name": "Updatable MAS",
            "agents": [{"agent_id": "agent-1"}],
        }
        create_response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert create_response.status_code == 201
        mas_id = create_response.json()["id"]

        update_data = {
            "agents": [
                {
                    "agent_id": "agent-1",
                    "name": "Updated Agent",
                    "url": "http://agent-1:9000",
                    "identity": {
                        "type": "openclaw",
                        "identifiers": {"url": "main::agents::agent-1"},
                    },
                },
            ],
        }
        update_response = client.put(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}", json=update_data
        )
        assert update_response.status_code == 200
        agent = update_response.json()["agents"][0]

        assert agent["agent_id"] == "agent-1"
        assert agent["name"] == "Updated Agent"
        assert agent["url"] == "http://agent-1:9000"
        assert agent["identity"]["type"] == "openclaw"
        assert agent["identity"]["identifiers"] == {"url": "main::agents::agent-1"}

    def test_create_mas_custom_identity_type(self, client, created_workspace):
        """Test that any string is accepted as identity type."""
        mas_data = {
            "name": "Custom Identity MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "identity": {
                        "type": "foo/bar",
                        "identifiers": {"key": "value"},
                    },
                },
            ],
        }

        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert response.status_code == 201

    def test_list_mas_includes_agent_identity_fields(self, client, created_workspace):
        """Test that listing MAS returns agent identity fields."""
        mas_data = {
            "name": "Listed MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "name": "My Agent",
                    "url": "http://my-agent:8080",
                    "identity": {
                        "type": "claude_code",
                        "identifiers": {"org_id": "10", "project_id": "20"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        list_response = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems")
        assert list_response.status_code == 200
        systems = list_response.json()["systems"]
        assert len(systems) == 1

        agent = systems[0]["agents"][0]
        assert agent["name"] == "My Agent"
        assert agent["url"] == "http://my-agent:8080"
        assert agent["identity"]["type"] == "claude_code"
        assert agent["identity"]["identifiers"] == {"org_id": "10", "project_id": "20"}
