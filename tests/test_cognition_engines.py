# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for Cognition Engine API endpoints"""

import pytest
from fastapi import status


class TestCognitionEngineCreate:
    """Test cognition engine creation with different configurations"""

    def test_create_cognition_engine_invalid_workspace(self, client):
        """Test creating cognition engine with non-existent workspace"""
        payload = {
            "name": "test-engine",
            "config": {"type": "reasoning"},
        }

        response = client.post(
            "/api/workspaces/non-existent-workspace-id/cognition-engines",
            json=payload,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "workspace not found" in response.json()["detail"].lower()

    def test_create_cognition_engine_basic(self, client, created_workspace):
        """Test creating cognition engine with basic configuration"""
        payload = {
            "name": "reasoning-engine",
            "config": {
                "type": "reasoning",
                "model": "gpt-4",
                "temperature": 0.7,
            },
        }

        response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json=payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "reasoning-engine"
        assert data["workspace_id"] == created_workspace
        assert data["config"]["type"] == "reasoning"
        assert data["config"]["model"] == "gpt-4"
        assert data["enabled"] is True
        assert "id" in data
        assert "created_at" in data
        assert "created_by" in data

    def test_create_cognition_engine_planning(self, client, created_workspace):
        """Test creating planning engine"""
        payload = {
            "name": "planning-engine",
            "config": {
                "type": "planning",
                "horizon": "short-term",
                "max_steps": 10,
            },
        }

        response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json=payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "planning-engine"
        assert data["config"]["type"] == "planning"
        assert data["config"]["horizon"] == "short-term"

    def test_create_cognition_engine_no_config(self, client, created_workspace):
        """Test creating cognition engine without config"""
        payload = {
            "name": "simple-engine",
        }

        response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json=payload,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "simple-engine"
        assert data["config"] is None
        assert data["enabled"] is True

    def test_create_cognition_engine_duplicate_name(self, client, created_workspace):
        """Test that duplicate engine names within same workspace are rejected"""
        payload = {
            "name": "duplicate-test",
            "config": {"type": "test"},
        }

        # Create first engine
        response1 = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json=payload,
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to create duplicate
        response2 = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json=payload,
        )
        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response2.json()["detail"].lower()

    def test_create_cognition_engine_different_workspaces(
        self, client, registered_cfn
    ):
        """Test that same engine name can exist in different workspaces"""
        # Create two workspaces
        ws1_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 1", "cfn_id": registered_cfn},
        )
        ws1_id = ws1_response.json()["id"]

        ws2_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 2", "cfn_id": registered_cfn},
        )
        ws2_id = ws2_response.json()["id"]

        payload = {
            "name": "shared-name-engine",
            "config": {"type": "test"},
        }

        # Create engine in workspace 1
        response1 = client.post(
            f"/api/workspaces/{ws1_id}/cognition-engines",
            json=payload,
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Create engine with same name in workspace 2 - should succeed
        response2 = client.post(
            f"/api/workspaces/{ws2_id}/cognition-engines",
            json=payload,
        )
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.json()["workspace_id"] == ws2_id


class TestCognitionEngineList:
    """Test cognition engine listing"""

    def test_list_cognition_engines_invalid_workspace(self, client):
        """Test listing cognition engines with non-existent workspace"""
        response = client.get(
            "/api/workspaces/non-existent-workspace-id/cognition-engines"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "workspace not found" in response.json()["detail"].lower()

    def test_list_cognition_engines_empty(self, client, created_workspace):
        """Test listing when no engines exist"""
        response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
        assert data["engines"] == []

    def test_list_cognition_engines(self, client, created_workspace):
        """Test listing cognition engines"""
        # Create multiple engines
        engines = [
            {
                "name": "reasoning-engine",
                "config": {"type": "reasoning"},
            },
            {
                "name": "planning-engine",
                "config": {"type": "planning"},
            },
            {
                "name": "learning-engine",
                "config": {"type": "learning"},
            },
        ]

        for engine in engines:
            response = client.post(
                f"/api/workspaces/{created_workspace}/cognition-engines",
                json=engine,
            )
            assert response.status_code == status.HTTP_201_CREATED

        # List engines
        response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
        assert len(data["engines"]) == 3

        # Verify all engines are present
        engine_names = [e["name"] for e in data["engines"]]
        assert "reasoning-engine" in engine_names
        assert "planning-engine" in engine_names
        assert "learning-engine" in engine_names

    def test_list_only_shows_enabled_engines(self, client, created_workspace):
        """Test that listing only returns enabled engines"""
        # Create two engines
        client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "enabled-engine"},
        )

        disabled_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "disabled-engine"},
        )
        disabled_id = disabled_response.json()["id"]

        # Disable one engine
        client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{disabled_id}",
            json={"enabled": False},
        )

        # List should only show enabled engine
        response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["engines"][0]["name"] == "enabled-engine"

    def test_list_engines_workspace_isolation(self, client, registered_cfn):
        """Test that listing only shows engines from specific workspace"""
        # Create two workspaces
        ws1_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 1", "cfn_id": registered_cfn},
        )
        ws1_id = ws1_response.json()["id"]

        ws2_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 2", "cfn_id": registered_cfn},
        )
        ws2_id = ws2_response.json()["id"]

        # Create engine in workspace 1
        client.post(
            f"/api/workspaces/{ws1_id}/cognition-engines",
            json={"name": "ws1-engine"},
        )

        # Create engine in workspace 2
        client.post(
            f"/api/workspaces/{ws2_id}/cognition-engines",
            json={"name": "ws2-engine"},
        )

        # List engines in workspace 1
        response1 = client.get(f"/api/workspaces/{ws1_id}/cognition-engines")
        data1 = response1.json()
        assert data1["total"] == 1
        assert data1["engines"][0]["name"] == "ws1-engine"

        # List engines in workspace 2
        response2 = client.get(f"/api/workspaces/{ws2_id}/cognition-engines")
        data2 = response2.json()
        assert data2["total"] == 1
        assert data2["engines"][0]["name"] == "ws2-engine"


class TestCognitionEngineGet:
    """Test getting individual cognition engine"""

    def test_get_cognition_engine_invalid_workspace(self, client):
        """Test getting cognition engine with non-existent workspace"""
        response = client.get(
            "/api/workspaces/non-existent-workspace-id/cognition-engines/some-engine-id"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "workspace not found" in response.json()["detail"].lower()

    def test_get_cognition_engine(self, client, created_workspace):
        """Test getting a specific cognition engine"""
        # Create engine
        create_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={
                "name": "test-engine",
                "config": {"type": "reasoning", "model": "gpt-4"},
            },
        )
        engine_id = create_response.json()["id"]

        # Get engine
        response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == engine_id
        assert data["name"] == "test-engine"
        assert data["workspace_id"] == created_workspace
        assert data["config"]["type"] == "reasoning"
        assert data["enabled"] is True

    def test_get_nonexistent_cognition_engine(self, client, created_workspace):
        """Test getting an engine that doesn't exist"""
        response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines/nonexistent-id"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_engine_from_wrong_workspace(self, client, registered_cfn):
        """Test that you can't get an engine using wrong workspace_id"""
        # Create two workspaces
        ws1_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 1", "cfn_id": registered_cfn},
        )
        ws1_id = ws1_response.json()["id"]

        ws2_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 2", "cfn_id": registered_cfn},
        )
        ws2_id = ws2_response.json()["id"]

        # Create engine in workspace 1
        create_response = client.post(
            f"/api/workspaces/{ws1_id}/cognition-engines",
            json={"name": "ws1-engine"},
        )
        engine_id = create_response.json()["id"]

        # Try to get it from workspace 2
        response = client.get(
            f"/api/workspaces/{ws2_id}/cognition-engines/{engine_id}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCognitionEngineUpdate:
    """Test cognition engine updates"""

    def test_update_cognition_engine_invalid_workspace(self, client):
        """Test updating cognition engine with non-existent workspace"""
        response = client.patch(
            "/api/workspaces/non-existent-workspace-id/cognition-engines/some-engine-id",
            json={"name": "new-name"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "workspace not found" in response.json()["detail"].lower()

    def test_update_cognition_engine_name(self, client, created_workspace):
        """Test updating cognition engine name"""
        # Create engine
        create_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "old-name"},
        )
        engine_id = create_response.json()["id"]

        # Update name
        update_payload = {"name": "new-name"}
        response = client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json=update_payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "new-name"
        assert "updated_at" in data
        assert "updated_by" in data

    def test_update_cognition_engine_config(self, client, created_workspace):
        """Test updating cognition engine configuration"""
        # Create engine
        create_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={
                "name": "update-config-test",
                "config": {"type": "reasoning", "model": "gpt-3.5"},
            },
        )
        engine_id = create_response.json()["id"]

        # Update config
        update_payload = {
            "config": {
                "type": "reasoning",
                "model": "gpt-4",
                "temperature": 0.8,
                "max_tokens": 2000,
            }
        }
        response = client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json=update_payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["config"]["model"] == "gpt-4"
        assert data["config"]["temperature"] == 0.8
        assert data["config"]["max_tokens"] == 2000

    def test_update_cognition_engine_enable_disable(self, client, created_workspace):
        """Test enabling/disabling cognition engine"""
        # Create engine
        create_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "disable-test"},
        )
        engine_id = create_response.json()["id"]

        # Disable engine
        response = client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json={"enabled": False},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["enabled"] is False

        # Re-enable engine
        response = client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json={"enabled": True},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["enabled"] is True

    def test_update_multiple_fields(self, client, created_workspace):
        """Test updating multiple fields at once"""
        # Create engine
        create_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={
                "name": "multi-update-test",
                "config": {"type": "old"},
            },
        )
        engine_id = create_response.json()["id"]

        # Update multiple fields
        update_payload = {
            "name": "multi-updated",
            "config": {"type": "new", "version": "2.0"},
            "enabled": False,
        }
        response = client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json=update_payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "multi-updated"
        assert data["config"]["type"] == "new"
        assert data["config"]["version"] == "2.0"
        assert data["enabled"] is False

    def test_update_nonexistent_engine(self, client, created_workspace):
        """Test updating an engine that doesn't exist"""
        response = client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/nonexistent-id",
            json={"name": "new-name"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCognitionEngineDelete:
    """Test cognition engine deletion"""

    def test_delete_cognition_engine_invalid_workspace(self, client):
        """Test deleting cognition engine with non-existent workspace"""
        response = client.delete(
            "/api/workspaces/non-existent-workspace-id/cognition-engines/some-engine-id"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "workspace not found" in response.json()["detail"].lower()

    def test_delete_cognition_engine(self, client, created_workspace):
        """Test deleting a cognition engine"""
        # Create engine
        create_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "delete-test"},
        )
        engine_id = create_response.json()["id"]

        # Delete engine
        response = client.delete(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}"
        )

        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"].lower()
        assert response.json()["id"] == engine_id

        # Verify it's deleted (soft delete)
        get_response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}"
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_engine(self, client, created_workspace):
        """Test deleting an engine that doesn't exist"""
        response = client.delete(
            f"/api/workspaces/{created_workspace}/cognition-engines/nonexistent-id"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deleted_engine_not_in_list(self, client, created_workspace):
        """Test that deleted engines don't appear in list"""
        # Create two engines
        client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "keep-engine"},
        )

        delete_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "delete-engine"},
        )
        delete_id = delete_response.json()["id"]

        # Delete one
        client.delete(
            f"/api/workspaces/{created_workspace}/cognition-engines/{delete_id}"
        )

        # List should only show the non-deleted engine
        list_response = client.get(
            f"/api/workspaces/{created_workspace}/cognition-engines"
        )
        data = list_response.json()
        assert data["total"] == 1
        assert data["engines"][0]["name"] == "keep-engine"


class TestCognitionEngineCFNIntegration:
    """Test integration with CFN config generation"""

    def test_engines_in_cfn_config(self, client, created_workspace):
        """Test that cognition engines appear in CFN configuration"""
        # Get the CFN ID for this workspace
        workspace_response = client.get(f"/api/workspaces/{created_workspace}")
        cfn_id = workspace_response.json()["cfn_id"]

        # Create cognition engines
        engine1_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={
                "name": "reasoning-engine",
                "config": {"type": "reasoning", "model": "gpt-4"},
            },
        )
        engine1_id = engine1_response.json()["id"]

        engine2_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={
                "name": "planning-engine",
                "config": {"type": "planning", "horizon": "long-term"},
            },
        )
        engine2_id = engine2_response.json()["id"]

        # Get CFN config
        cfn_config_response = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert cfn_config_response.status_code == status.HTTP_200_OK

        cfn_config = cfn_config_response.json()
        assert "config" in cfn_config
        assert "workspaces" in cfn_config["config"]

        # Find our workspace in the config
        workspaces = cfn_config["config"]["workspaces"]
        test_workspace = next(
            (ws for ws in workspaces if ws["workspace_id"] == created_workspace), None
        )
        assert test_workspace is not None

        # Verify cognition engines are in the config
        assert "cognition_engines" in test_workspace
        engines = test_workspace["cognition_engines"]
        assert len(engines) == 2

        # Verify engine details
        engine_ids = [e["id"] for e in engines]
        assert engine1_id in engine_ids
        assert engine2_id in engine_ids

        # Verify engine configs are present
        reasoning_engine = next(
            (e for e in engines if e["name"] == "reasoning-engine"),
            None,
        )
        assert reasoning_engine is not None
        assert reasoning_engine["config"]["type"] == "reasoning"
        assert reasoning_engine["config"]["model"] == "gpt-4"
        assert reasoning_engine["enabled"] is True

    def test_disabled_engines_not_in_cfn_config(self, client, created_workspace):
        """Test that disabled engines don't appear in CFN config"""
        # Get the CFN ID for this workspace
        workspace_response = client.get(f"/api/workspaces/{created_workspace}")
        cfn_id = workspace_response.json()["cfn_id"]

        # Create and disable an engine
        engine_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "disabled-engine"},
        )
        engine_id = engine_response.json()["id"]

        client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json={"enabled": False},
        )

        # Get CFN config
        cfn_config_response = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        cfn_config = cfn_config_response.json()

        # Find our workspace
        workspaces = cfn_config["config"]["workspaces"]
        test_workspace = next(
            (ws for ws in workspaces if ws["workspace_id"] == created_workspace), None
        )

        # Verify no engines in config (disabled engine should not appear)
        engines = test_workspace.get("cognition_engines", [])
        assert len(engines) == 0

    def test_engine_update_triggers_cfn_config_update(self, client, created_workspace):
        """Test that updating an engine updates the CFN configuration"""
        # Get the CFN ID
        workspace_response = client.get(f"/api/workspaces/{created_workspace}")
        cfn_id = workspace_response.json()["cfn_id"]

        # Create engine
        engine_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={
                "name": "test-engine",
                "config": {"version": "1.0"},
            },
        )
        engine_id = engine_response.json()["id"]

        # Update engine
        client.patch(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}",
            json={"config": {"version": "2.0"}},
        )

        # Get updated CFN config
        cfn_config = client.get(f"/api/cognition-fabric-nodes/{cfn_id}").json()

        # Verify updated config is in CFN config
        workspaces = cfn_config["config"]["workspaces"]
        test_workspace = next(
            (ws for ws in workspaces if ws["workspace_id"] == created_workspace), None
        )
        engines = test_workspace["cognition_engines"]
        test_engine = next(
            (e for e in engines if e["id"] == engine_id), None
        )
        assert test_engine is not None
        assert test_engine["config"]["version"] == "2.0"

    def test_engine_delete_triggers_cfn_config_update(self, client, created_workspace):
        """Test that deleting an engine removes it from CFN configuration"""
        # Get the CFN ID
        workspace_response = client.get(f"/api/workspaces/{created_workspace}")
        cfn_id = workspace_response.json()["cfn_id"]

        # Create engine
        engine_response = client.post(
            f"/api/workspaces/{created_workspace}/cognition-engines",
            json={"name": "delete-me"},
        )
        engine_id = engine_response.json()["id"]

        # Verify engine is in CFN config
        cfn_config_before = client.get(f"/api/cognition-fabric-nodes/{cfn_id}").json()
        workspaces_before = cfn_config_before["config"]["workspaces"]
        test_workspace_before = next(
            (ws for ws in workspaces_before if ws["workspace_id"] == created_workspace),
            None,
        )
        engines_before = test_workspace_before.get("cognition_engines", [])
        engine_ids_before = [e["id"] for e in engines_before]
        assert engine_id in engine_ids_before

        # Delete engine
        client.delete(
            f"/api/workspaces/{created_workspace}/cognition-engines/{engine_id}"
        )

        # Get updated CFN config
        cfn_config_after = client.get(f"/api/cognition-fabric-nodes/{cfn_id}").json()

        # Verify engine is removed from CFN config
        workspaces_after = cfn_config_after["config"]["workspaces"]
        test_workspace_after = next(
            (ws for ws in workspaces_after if ws["workspace_id"] == created_workspace),
            None,
        )
        engines_after = test_workspace_after.get("cognition_engines", [])
        engine_ids_after = [e["id"] for e in engines_after]
        assert engine_id not in engine_ids_after
