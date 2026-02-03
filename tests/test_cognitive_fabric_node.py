"""Tests for Cognitive Fabric Node endpoints"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


class TestCognitiveFabricNodeRegistration:
    """Test cases for Cognitive Fabric Node registration"""

    def test_register_cfn_success(self, client):
        """Test successful CFN registration"""
        # First create a workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        assert ws_response.status_code == 201
        workspace_id = ws_response.json()["id"]

        # Register CFN
        cfn_data = {
            "cfn_id": "cfn-test-node-123",
            "cfn_name": "test-cfn-node",
            "cfn_config": {"memory": "4GB", "max_connections": 100},
        }

        response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)

        assert response.status_code == 201
        data = response.json()
        assert data["cfn_id"] == "cfn-test-node-123"
        assert data["cfn_name"] == "test-cfn-node"
        assert data["status"] == "offline"  # Starts offline, heartbeat makes it online
        assert "cloud_config" in data
        assert data["cloud_config"]["workspace_id"] == workspace_id
        assert "log_level" in data["cloud_config"]

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-test-node-123/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_register_cfn_duplicate_id(self, client):
        """Test registering CFN with duplicate cfn_id"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-duplicate-123", "cfn_name": "test-cfn-1"}

        # First registration
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)
        assert response1.status_code == 201

        # Second registration with same cfn_id
        response2 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)
        assert response2.status_code == 409  # Conflict

    def test_register_cfn_duplicate_name_same_workspace(self, client):
        """Test registering CFN with duplicate name in same workspace"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # First CFN
        response1 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-1", "cfn_name": "duplicate-name"},
        )
        assert response1.status_code == 201

        # Second CFN with different ID but same name
        response2 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-2", "cfn_name": "duplicate-name"},
        )
        assert response2.status_code == 409  # Conflict

    def test_register_cfn_same_name_different_workspaces(self, client):
        """Test registering CFN with same name in different workspaces (should succeed)"""
        # Create two workspaces
        ws1_response = client.post("/api/workspaces", json={"name": "Workspace 1"})
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws1_id = ws1_response.json()["id"]
        ws2_id = ws2_response.json()["id"]

        # Register CFN in workspace 1
        response1 = client.post(
            f"/api/workspaces/{ws1_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-ws1", "cfn_name": "shared-name"},
        )
        assert response1.status_code == 201

        # Register CFN with same name in workspace 2 (should succeed)
        response2 = client.post(
            f"/api/workspaces/{ws2_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-ws2", "cfn_name": "shared-name"},
        )
        assert response2.status_code == 201

    def test_register_cfn_nonexistent_workspace(self, client):
        """Test registering CFN in non-existent workspace"""
        response = client.post(
            "/api/workspaces/nonexistent-workspace-id/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-test", "cfn_name": "test"},
        )
        assert response.status_code == 404


class TestCognitiveFabricNodeHeartbeat:
    """Test cases for Cognitive Fabric Node heartbeat"""

    def test_cfn_heartbeat_success(self, client, registered_cfn):
        """Test successful CFN heartbeat"""
        workspace_id, cfn_id = registered_cfn

        response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "last_seen" in data

    def test_cfn_heartbeat_after_deregistration(self, client, registered_cfn):
        """Test heartbeat after CFN is de-registered (should fail)"""
        workspace_id, cfn_id = registered_cfn

        # De-register CFN
        delete_response = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert delete_response.status_code == 204

        # Try heartbeat (should fail)
        response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat")
        assert response.status_code == 403

    def test_cfn_heartbeat_nonexistent_node(self, client):
        """Test heartbeat for non-existent CFN"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/nonexistent-cfn-id/heartbeat")
        assert response.status_code == 404


class TestCognitiveFabricNodeList:
    """Test cases for listing Cognitive Fabric Nodes"""

    def test_list_cfn_nodes_empty(self, client):
        """Test listing CFN nodes in empty workspace"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 0
        assert data["total"] == 0

    def test_list_cfn_nodes(self, client, multiple_cfn_nodes):
        """Test listing CFN nodes"""
        workspace_id, cfn_ids = multiple_cfn_nodes

        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")

        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 3
        assert data["total"] == 3

        # Verify each node has required fields
        for node in data["nodes"]:
            assert "cfn_id" in node
            assert "workspace_id" in node
            assert "cfn_name" in node
            assert "status" in node
            assert "last_seen" in node
            assert "enabled" in node
            assert "created_at" in node

    def test_list_cfn_nodes_with_status_filter(self, client, registered_cfn):
        """Test listing CFN nodes with status filter"""
        workspace_id, _ = registered_cfn

        # List online nodes
        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node?status=online")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for node in data["nodes"]:
            assert node["status"] == "online"

    def test_list_cfn_workspace_isolation(self, client):
        """Test CFN nodes are isolated by workspace"""
        # Create two workspaces
        ws1_response = client.post("/api/workspaces", json={"name": "Workspace 1"})
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws1_id = ws1_response.json()["id"]
        ws2_id = ws2_response.json()["id"]

        # Register CFN in ws1
        client.post(
            f"/api/workspaces/{ws1_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-ws1", "cfn_name": "cfn-1"},
        )

        # List CFN in ws2 should be empty
        response = client.get(f"/api/workspaces/{ws2_id}/cognitive-fabric-node")
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestCognitiveFabricNodeGet:
    """Test cases for getting Cognitive Fabric Node details"""

    def test_get_cfn_details(self, client, registered_cfn):
        """Test getting CFN node details"""
        workspace_id, cfn_id = registered_cfn

        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["cfn_id"] == cfn_id
        assert data["workspace_id"] == workspace_id
        assert "cfn_name" in data
        assert "cloud_config" in data
        assert "cfn_config" in data
        assert "status" in data
        assert "last_seen" in data
        assert "enabled" in data
        assert "created_at" in data

    def test_get_cfn_nonexistent(self, client):
        """Test getting non-existent CFN"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/nonexistent-cfn")
        assert response.status_code == 404

    def test_get_cfn_wrong_workspace(self, client, registered_cfn):
        """Test getting CFN from wrong workspace"""
        _, cfn_id = registered_cfn

        # Create different workspace
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws2_id = ws2_response.json()["id"]

        # Try to get CFN from wrong workspace
        response = client.get(f"/api/workspaces/{ws2_id}/cognitive-fabric-node/{cfn_id}")
        assert response.status_code == 403


class TestCognitiveFabricNodeUpdate:
    """Test cases for updating Cognitive Fabric Node"""

    def test_update_cfn_name(self, client, registered_cfn):
        """Test updating CFN name"""
        workspace_id, cfn_id = registered_cfn

        update_data = {"cfn_name": "updated-cfn-name"}

        response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cfn_name"] == "updated-cfn-name"

    def test_update_cfn_config(self, client, registered_cfn):
        """Test updating CFN config"""
        workspace_id, cfn_id = registered_cfn

        update_data = {"cfn_config": {"memory": "8GB", "max_connections": 200}}

        response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cfn_config"]["memory"] == "8GB"
        assert data["cfn_config"]["max_connections"] == 200

    def test_update_cfn_duplicate_name(self, client, multiple_cfn_nodes):
        """Test updating CFN with duplicate name in same workspace"""
        workspace_id, cfn_ids = multiple_cfn_nodes

        # Try to rename cfn_ids[0] to the name of cfn_ids[1]
        # First get the name of cfn_ids[1]
        get_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_ids[1]}")
        existing_name = get_response.json()["cfn_name"]

        # Try to update cfn_ids[0] with that name
        response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_ids[0]}",
            json={"cfn_name": existing_name},
        )
        assert response.status_code == 409

    def test_update_cfn_nonexistent(self, client):
        """Test updating non-existent CFN"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/nonexistent-cfn",
            json={"cfn_name": "new-name"},
        )
        assert response.status_code == 404


class TestCognitiveFabricNodeDeregistration:
    """Test cases for Cognitive Fabric Node de-registration"""

    def test_deregister_cfn(self, client, registered_cfn):
        """Test de-registering CFN node"""
        workspace_id, cfn_id = registered_cfn

        response = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")

        assert response.status_code == 204

        # Verify CFN no longer appears in list
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        assert list_response.json()["total"] == 0

    def test_deregister_cfn_twice(self, client, registered_cfn):
        """Test de-registering CFN twice (should fail second time)"""
        workspace_id, cfn_id = registered_cfn

        # First de-registration
        response1 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert response1.status_code == 204

        # Second de-registration (should fail)
        response2 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert response2.status_code == 404

    def test_deregister_cfn_nonexistent(self, client):
        """Test de-registering non-existent CFN"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/nonexistent-cfn")
        assert response.status_code == 404


class TestCognitiveFabricNodeReregistration:
    """Test cases for Cognitive Fabric Node re-registration"""

    def test_reregister_cfn_after_deregistration(self, client):
        """Test re-registering a CFN after it was de-registered"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Initial registration
        cfn_data = {
            "cfn_id": "cfn-reregister-test",
            "cfn_name": "test-node",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)
        assert response1.status_code == 201
        assert response1.json()["status"] == "offline"  # Starts offline

        # De-register
        response2 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reregister-test")
        assert response2.status_code == 204

        # Verify it's not in the list
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        assert list_response.json()["total"] == 0

        # Re-register with updated config using the new endpoint
        updated_cfn_data = {
            "cfn_id": "cfn-reregister-test",
            "cfn_name": "test-node-updated",
            "cfn_config": {"memory": "8GB"},
        }
        response3 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json=updated_cfn_data,
        )
        assert response3.status_code == 201
        data = response3.json()
        assert data["cfn_id"] == "cfn-reregister-test"
        assert data["cfn_name"] == "test-node-updated"
        assert data["status"] == "offline"  # Re-registration also starts offline
        assert "cloud_config" in data

        # Verify it's back in the list
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        assert list_response.json()["total"] == 1

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reregister-test/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

        # Verify updated details
        detail_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reregister-test")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["cfn_name"] == "test-node-updated"
        assert detail["cfn_config"]["memory"] == "8GB"
        assert detail["enabled"] is True
        assert detail["status"] == "online"  # Now online after heartbeat

    def test_reregister_cfn_with_same_config(self, client):
        """Test re-registering a CFN with the same configuration"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-same-config", "cfn_name": "same-config-node"}

        # Register
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)
        assert response1.status_code == 201

        # De-register
        client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-same-config")

        # Re-register with same config using the reregister endpoint
        response2 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data
        )
        assert response2.status_code == 201
        assert response2.json()["cfn_id"] == "cfn-same-config"
        assert response2.json()["status"] == "offline"  # Re-registration starts offline

    def test_reregister_cfn_name_conflict(self, client):
        """Test re-registering a CFN when another CFN already has the desired name"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Register first CFN
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-first", "cfn_name": "first-node"},
        )

        # Register second CFN
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-second", "cfn_name": "second-node"},
        )

        # De-register second CFN
        client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-second")

        # Try to re-register second CFN with first CFN's name (should fail)
        response = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-second", "cfn_name": "first-node"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_reregister_cfn_different_workspace(self, client):
        """Test re-registering a CFN in a different workspace (should fail)"""
        # Create two workspaces
        ws1_response = client.post("/api/workspaces", json={"name": "Workspace 1"})
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws1_id = ws1_response.json()["id"]
        ws2_id = ws2_response.json()["id"]

        # Register CFN in workspace 1
        cfn_data = {"cfn_id": "cfn-workspace-test", "cfn_name": "test-node"}
        response1 = client.post(f"/api/workspaces/{ws1_id}/cognitive-fabric-node/register", json=cfn_data)
        assert response1.status_code == 201

        # De-register from workspace 1
        client.delete(f"/api/workspaces/{ws1_id}/cognitive-fabric-node/cfn-workspace-test")

        # Try to re-register in workspace 2 (should fail)
        response2 = client.post(
            f"/api/workspaces/{ws2_id}/cognitive-fabric-node/register", json=cfn_data
        )
        assert response2.status_code == 403
        assert "different workspace" in response2.json()["detail"]

    def test_reregister_cfn_heartbeat_works(self, client):
        """Test that heartbeat works after re-registration"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-heartbeat-test", "cfn_name": "heartbeat-node"}

        # Register
        client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)

        # De-register
        client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-heartbeat-test")

        # Re-register using the reregister endpoint
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data
        )

        # Send heartbeat (should work)
        heartbeat_response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-heartbeat-test/heartbeat"
        )
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_disabled_cfn_cannot_heartbeat_until_reregistered(self, client):
        """Test that a de-registered (disabled) CFN cannot send heartbeats until re-registered"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-disabled-test", "cfn_name": "disabled-node"}

        # Register
        client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)

        # De-register
        client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled-test")

        # Try to send heartbeat (should fail - disabled)
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled-test/heartbeat")
        assert heartbeat_response.status_code == 403
        assert "disabled" in heartbeat_response.json()["detail"]

        # Re-register using the reregister endpoint
        client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)

        # Now heartbeat should work
        heartbeat_response2 = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled-test/heartbeat"
        )
        assert heartbeat_response2.status_code == 200

    def test_register_already_active_cfn_fails(self, client):
        """Test that registering an already active CFN fails"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-active-test", "cfn_name": "active-node"}

        # Register
        client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)

        # Try to register again without de-registering first (should fail)
        response = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]


class TestCognitiveFabricNodeBackgroundMonitoring:
    """Test cases for CFN background monitoring (marking stale nodes offline)"""

    def test_mark_stale_nodes_offline(self, client):
        """Test that stale nodes are marked offline"""
        # This test would require mocking time or waiting
        # For now, we'll test the service method directly
        from server.services.cognitive_fabric_node import cognitive_fabric_node_service

        # Create workspace and register CFN
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        register_response = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register",
            json={"cfn_id": "cfn-stale-test", "cfn_name": "stale-node"},
        )
        assert register_response.json()["status"] == "offline"  # Starts offline

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-stale-test/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

        # Manually call mark_stale_nodes_offline with 0 minute threshold
        # (should mark the online node as offline immediately since last_seen is in the past)
        count = cognitive_fabric_node_service.mark_stale_nodes_offline(threshold_minutes=0)

        # Should mark at least one node as offline
        assert count >= 1

        # Verify node is offline
        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-stale-test")
        assert response.status_code == 200
        assert response.json()["status"] == "offline"


# Pytest fixtures


@pytest.fixture
def registered_cfn(client):
    """Fixture: Register a CFN, send heartbeat to make it online, and return workspace_id, cfn_id"""
    ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    workspace_id = ws_response.json()["id"]

    cfn_data = {"cfn_id": "cfn-fixture-123", "cfn_name": "fixture-cfn-node"}

    response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)
    assert response.status_code == 201
    assert response.json()["status"] == "offline"  # Initially offline

    # Send heartbeat to make it online
    heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_data['cfn_id']}/heartbeat")
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["status"] == "online"  # Now online

    return workspace_id, cfn_data["cfn_id"]


@pytest.fixture
def multiple_cfn_nodes(client):
    """Fixture: Register multiple CFN nodes, send heartbeats to make them online, and return workspace_id, [cfn_ids]"""
    ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    workspace_id = ws_response.json()["id"]

    cfn_ids = []
    for i in range(3):
        cfn_data = {"cfn_id": f"cfn-multi-{i}", "cfn_name": f"cfn-node-{i}"}
        response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/register", json=cfn_data)
        assert response.status_code == 201

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_data['cfn_id']}/heartbeat")
        assert heartbeat_response.status_code == 200

        cfn_ids.append(cfn_data["cfn_id"])

    return workspace_id, cfn_ids
