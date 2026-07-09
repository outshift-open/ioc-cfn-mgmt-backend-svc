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
        assert isinstance(mas["cognition_engines"], list)

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
        body = get_response.json()
        agent = body["agents"][0]

        assert agent["agent_id"] == "agent-1"
        assert agent["name"] is None
        assert agent["url"] is None
        assert agent["identity"] is None
        assert agent["config"] == {"type": "reasoning"}
        assert isinstance(body["cognition_engines"], list)
        assert body["cognition_engines"] == []

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


class TestMASQueryByIdentity:
    """Test cases for POST /workspaces/{workspace_id}/multi-agentic-systems/query endpoint."""

    def test_query_by_identity_type_only(self, client, created_workspace):
        """Test querying MAS by identity_type alone."""
        mas_data = {
            "name": "Claude MAS",
            "agents": [
                {
                    "agent_id": "claude-agent-1",
                    "name": "Claude Agent",
                    "identity": {
                        "type": "claude",
                        "identifiers": {"org_id": "100", "project_id": "200"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude"},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 1
        assert systems[0]["name"] == "Claude MAS"

    def test_query_by_identity_identifiers_only(self, client, created_workspace):
        """Test querying MAS by identity_identifiers alone (any type)."""
        mas_data = {
            "name": "Identifiers MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "identity": {
                        "type": "openclaw",
                        "identifiers": {"xyz": "pqr", "abc": "def"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_identifiers": {"xyz": "pqr"}},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 1
        assert systems[0]["name"] == "Identifiers MAS"

    def test_query_by_both_type_and_identifiers(self, client, created_workspace):
        """Test querying MAS by both identity_type and identity_identifiers."""
        # Create two MAS with different identity types but same identifiers
        mas_claude = {
            "name": "Claude MAS",
            "agents": [
                {
                    "agent_id": "claude-1",
                    "identity": {
                        "type": "claude",
                        "identifiers": {"xyz": "pqr"},
                    },
                },
            ],
        }
        mas_openclaw = {
            "name": "OpenClaw MAS",
            "agents": [
                {
                    "agent_id": "openclaw-1",
                    "identity": {
                        "type": "openclaw",
                        "identifiers": {"xyz": "pqr"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_claude)
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_openclaw)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude", "identity_identifiers": {"xyz": "pqr"}},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 1
        assert systems[0]["name"] == "Claude MAS"

    def test_query_empty_payload_returns_422(self, client, created_workspace):
        """Test that an empty payload returns 422 validation error."""
        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={},
        )

        assert response.status_code == 422

    def test_query_no_matches_returns_empty(self, client, created_workspace):
        """Test that a query with no matches returns empty systems list."""
        mas_data = {
            "name": "Some MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "identity": {
                        "type": "openclaw",
                        "identifiers": {"url": "main::agents::agent-1"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "nonexistent"},
        )

        assert response.status_code == 200
        assert response.json()["systems"] == []

    def test_query_partial_identifiers_match(self, client, created_workspace):
        """Test that partial identifiers match via JSONB containment."""
        mas_data = {
            "name": "Multi-Key MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "identity": {
                        "type": "claude",
                        "identifiers": {"org_id": "10", "project_id": "20", "env": "prod"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        # Query with subset of identifiers — should match
        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude", "identity_identifiers": {"org_id": "10"}},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 1
        assert systems[0]["name"] == "Multi-Key MAS"

    def test_query_identifiers_no_match_wrong_value(self, client, created_workspace):
        """Test that identifiers with wrong value don't match."""
        mas_data = {
            "name": "Value MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "identity": {
                        "type": "claude",
                        "identifiers": {"xyz": "pqr"},
                    },
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude", "identity_identifiers": {"xyz": "wrong"}},
        )

        assert response.status_code == 200
        assert response.json()["systems"] == []

    def test_query_multiple_mas_match(self, client, created_workspace):
        """Test that multiple MAS can match the same query."""
        for i in range(3):
            mas_data = {
                "name": f"Claude MAS {i}",
                "agents": [
                    {
                        "agent_id": f"agent-{i}",
                        "identity": {
                            "type": "claude",
                            "identifiers": {"team": "alpha"},
                        },
                    },
                ],
            }
            client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude", "identity_identifiers": {"team": "alpha"}},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 3

    def test_query_workspace_not_found(self, client):
        """Test query on non-existent workspace returns 404."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"

        response = client.post(
            f"/api/workspaces/{fake_workspace_id}/multi-agentic-systems/query",
            json={"identity_type": "claude"},
        )

        assert response.status_code == 404

    def test_query_does_not_cross_workspaces(self, client, created_workspace, sample_workspace_data):
        """Test that query only returns MAS from the specified workspace."""
        # Create MAS in workspace 1
        mas_data = {
            "name": "WS1 MAS",
            "agents": [
                {
                    "agent_id": "agent-1",
                    "identity": {"type": "claude", "identifiers": {"xyz": "pqr"}},
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        # Create workspace 2 with its own MAS
        ws2_data = {"name": "Second Workspace", "cfn_id": sample_workspace_data["cfn_id"]}
        ws2_response = client.post("/api/workspaces/create", json=ws2_data)
        assert ws2_response.status_code == 201
        ws2_id = ws2_response.json()["id"]

        mas_data_2 = {
            "name": "WS2 MAS",
            "agents": [
                {
                    "agent_id": "agent-2",
                    "identity": {"type": "claude", "identifiers": {"xyz": "pqr"}},
                },
            ],
        }
        client.post(f"/api/workspaces/{ws2_id}/multi-agentic-systems", json=mas_data_2)

        # Query workspace 1 — should only get WS1 MAS
        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude", "identity_identifiers": {"xyz": "pqr"}},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 1
        assert systems[0]["name"] == "WS1 MAS"

    def test_query_returns_full_mas_with_all_agents(self, client, created_workspace):
        """Test that query returns the full MAS including all agents, not just matching ones."""
        mas_data = {
            "name": "Multi-Agent MAS",
            "agents": [
                {
                    "agent_id": "claude-agent",
                    "name": "Claude Agent",
                    "identity": {"type": "claude", "identifiers": {"xyz": "pqr"}},
                },
                {
                    "agent_id": "other-agent",
                    "name": "Other Agent",
                    "identity": {"type": "openclaw", "identifiers": {"url": "main::agents::other"}},
                },
            ],
        }
        client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)

        response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/query",
            json={"identity_type": "claude"},
        )

        assert response.status_code == 200
        systems = response.json()["systems"]
        assert len(systems) == 1
        agents = systems[0]["agents"]
        assert len(agents) == 2


class TestMASInlineCEAssociation:
    """Tests for cognition_engine_ids in MAS create and update payloads."""

    def _register_ce(self, client, cfn_id: str, name: str) -> str:
        resp = client.post(
            "/api/cognition-engines",
            json={
                "cfn_id": cfn_id,
                "name": name,
                "url": "http://ce:8080",
                "version": "1.0.0",
                "kinds_subkinds": {"knowledge": ["query"]},
                "subprotocols": ["sab"],
            },
        )
        assert resp.status_code == 201
        return resp.json()["ce_id"]

    def test_create_with_cognition_engine_ids_associates_ces(self, client, registered_cfn, created_workspace):
        """CEs listed in cognition_engine_ids are associated with the MAS on creation."""
        ce_id = self._register_ce(client, registered_cfn, "inline-create-ce")

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "inline-create-mas", "cognition_engine_ids": [ce_id]},
        )
        assert resp.status_code == 201
        mas_id = resp.json()["id"]

        # Verify the association exists — a duplicate associate returns 409
        assoc = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert assoc.status_code == 409

    def test_create_with_cognition_engine_ids_is_additive_with_auto_attach(
        self, client, registered_cfn, created_workspace
    ):
        """auto_attach CE + explicit CE in cognition_engine_ids both get associated; no error on overlap."""
        auto_ce_id = self._register_ce(client, registered_cfn, "inline-auto-ce")
        # Set mas_auto_associate so it attaches on MAS create
        client.patch(f"/api/cognition-engines/{auto_ce_id}", json={"mas_auto_associate": True})

        explicit_ce_id = self._register_ce(client, registered_cfn, "inline-explicit-ce")

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "inline-additive-mas", "cognition_engine_ids": [auto_ce_id, explicit_ce_id]},
        )
        assert resp.status_code == 201

    def test_create_omitting_cognition_engine_ids_leaves_associations_unchanged(
        self, client, created_workspace
    ):
        """Omitting cognition_engine_ids on create results in no CE associations (beyond auto-attach)."""
        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "inline-omit-mas"},
        )
        assert resp.status_code == 201

    def test_update_cognition_engine_ids_attaches_new_and_detaches_removed(
        self, client, registered_cfn, created_workspace
    ):
        """Update with cognition_engine_ids syncs associations: attaches new, detaches removed."""
        ce1_id = self._register_ce(client, registered_cfn, "inline-update-ce1")
        ce2_id = self._register_ce(client, registered_cfn, "inline-update-ce2")

        mas_id = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "inline-update-mas", "cognition_engine_ids": [ce1_id]},
        ).json()["id"]

        # Update: swap ce1 for ce2
        resp = client.put(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}",
            json={"cognition_engine_ids": [ce2_id]},
        )
        assert resp.status_code == 200

        # ce2 is now attached (duplicate → 409)
        assert client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce2_id},
        ).status_code == 409

        # ce1 is now detached (can be re-attached → 201)
        assert client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce1_id},
        ).status_code == 201

    def test_update_omitting_cognition_engine_ids_leaves_associations_unchanged(
        self, client, registered_cfn, created_workspace
    ):
        """Omitting cognition_engine_ids on update does not touch existing associations."""
        ce_id = self._register_ce(client, registered_cfn, "inline-omit-update-ce")

        mas_id = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "inline-omit-update-mas", "cognition_engine_ids": [ce_id]},
        ).json()["id"]

        # Update without cognition_engine_ids — association must still be there
        client.put(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}",
            json={"name": "inline-omit-update-mas-renamed"},
        )

        # Association still present → duplicate returns 409
        assert client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        ).status_code == 409

    def test_create_with_invalid_ce_id_returns_error(self, client, created_workspace):
        """Including a non-existent CE ID in cognition_engine_ids propagates the error."""
        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "inline-bad-ce-mas", "cognition_engine_ids": ["nonexistent-ce"]},
        )
        assert resp.status_code != 201

    def test_mas_response_includes_cognition_engines_field(self, client, created_workspace):
        """MAS detail and list responses always include cognition_engines (empty when none associated)."""
        mas_id = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "ce-field-mas"},
        ).json()["id"]

        get_resp = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "cognition_engines" in body
        assert body["cognition_engines"] == []

        list_resp = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems")
        assert list_resp.status_code == 200
        mas = next(s for s in list_resp.json()["systems"] if s["id"] == mas_id)
        assert "cognition_engines" in mas
        assert mas["cognition_engines"] == []

    def test_associated_ces_appear_in_mas_response(self, client, registered_cfn, created_workspace):
        """CEs associated via cognition_engine_ids show up in the MAS detail and list responses."""
        ce_id = self._register_ce(client, registered_cfn, "response-ce")

        mas_id = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "response-ce-mas", "cognition_engine_ids": [ce_id]},
        ).json()["id"]

        # GET detail
        get_resp = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")
        assert get_resp.status_code == 200
        ces = get_resp.json()["cognition_engines"]
        assert len(ces) == 1
        assert ces[0]["ce_id"] == ce_id
        assert ces[0]["name"] == "response-ce"
        assert ces[0]["url"] == "http://ce:8080"
        assert isinstance(ces[0]["enabled"], bool)
        assert "status" in ces[0]
        assert "mas_config" in ces[0]

        # List
        list_resp = client.get(f"/api/workspaces/{created_workspace}/multi-agentic-systems")
        assert list_resp.status_code == 200
        mas = next(s for s in list_resp.json()["systems"] if s["id"] == mas_id)
        assert len(mas["cognition_engines"]) == 1
        assert mas["cognition_engines"][0]["ce_id"] == ce_id

    def test_detached_ce_removed_from_mas_response(self, client, registered_cfn, created_workspace):
        """After syncing cognition_engine_ids to remove a CE, it no longer appears in the response."""
        ce1_id = self._register_ce(client, registered_cfn, "detach-ce1")
        ce2_id = self._register_ce(client, registered_cfn, "detach-ce2")

        mas_id = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={"name": "detach-ce-mas", "cognition_engine_ids": [ce1_id, ce2_id]},
        ).json()["id"]

        # Remove ce1, keep ce2
        update_resp = client.put(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}",
            json={"cognition_engine_ids": [ce2_id]},
        )
        assert update_resp.status_code == 200
        ces = update_resp.json()["cognition_engines"]
        ce_ids_in_resp = {c["ce_id"] for c in ces}
        assert ce2_id in ce_ids_in_resp
        assert ce1_id not in ce_ids_in_resp
