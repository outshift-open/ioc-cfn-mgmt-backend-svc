"""Tests for Cognitive Fabric Node endpoints"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


class TestCognitiveFabricNodeCreate:
    """Test cases for Cognitive Fabric Node registration"""

    def test_create_cfn_success(self, client):
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

        response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)

        assert response.status_code == 201
        data = response.json()
        assert data["cfn_id"] == "cfn-test-node-123"
        assert data["cfn_name"] == "test-cfn-node"
        assert data["status"] == "offline"  # Starts offline, heartbeat makes it online
        assert "cloud_config" in data
        assert data["cloud_config"]["metadata"]["workspace_id"] == workspace_id
        assert "metadata" in data["cloud_config"]

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-test-node-123/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_create_cfn_duplicate_id(self, client):
        """Test creating CFN with same cfn_id refreshes config (reboot scenario)"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-duplicate-123", "cfn_name": "test-cfn-1"}

        # First creation
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201

        # Second registration with same cfn_id (reboot scenario - refreshes config)
        response2 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response2.status_code == 201  # Refresh succeeds
        assert response2.json()["status"] == "offline"  # Back to offline after refresh

    def test_create_cfn_duplicate_name_same_workspace(self, client):
        """Test creating CFN with duplicate name in same workspace"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # First CFN
        response1 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-1", "cfn_name": "duplicate-name"},
        )
        assert response1.status_code == 201

        # Second CFN with different ID but same name
        response2 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-2", "cfn_name": "duplicate-name"},
        )
        assert response2.status_code == 409  # Conflict

    def test_create_cfn_same_name_different_workspaces(self, client):
        """Test creating CFN with same name in different workspaces (should succeed)"""
        # Create two workspaces
        ws1_response = client.post("/api/workspaces", json={"name": "Workspace 1"})
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws1_id = ws1_response.json()["id"]
        ws2_id = ws2_response.json()["id"]

        # Register CFN in workspace 1
        response1 = client.post(
            f"/api/workspaces/{ws1_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-ws1", "cfn_name": "shared-name"},
        )
        assert response1.status_code == 201

        # Register CFN with same name in workspace 2 (should succeed)
        response2 = client.post(
            f"/api/workspaces/{ws2_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-ws2", "cfn_name": "shared-name"},
        )
        assert response2.status_code == 201

    def test_create_cfn_nonexistent_workspace(self, client):
        """Test creating CFN in non-existent workspace"""
        response = client.post(
            "/api/workspaces/nonexistent-workspace-id/cognitive-fabric-node",
            json={"cfn_id": "cfn-test", "cfn_name": "test"},
        )
        assert response.status_code == 404


class TestCognitiveFabricNodeHeartbeat:
    """Test cases for Cognitive Fabric Node heartbeat"""

    def test_cfn_heartbeat_success(self, client, created_cfn):
        """Test successful CFN heartbeat"""
        workspace_id, cfn_id = created_cfn

        response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "last_seen" in data

    def test_cfn_heartbeat_after_disable(self, client, created_cfn):
        """Test heartbeat after CFN is disabled (should fail)"""
        workspace_id, cfn_id = created_cfn

        # Disable CFN
        disable_response = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable")
        assert disable_response.status_code == 200

        # Try heartbeat (should fail)
        response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat")
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"]

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

    def test_list_cfn_nodes_with_status_filter(self, client, created_cfn):
        """Test listing CFN nodes with status filter"""
        workspace_id, _ = created_cfn

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
            f"/api/workspaces/{ws1_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-ws1", "cfn_name": "cfn-1"},
        )

        # List CFN in ws2 should be empty
        response = client.get(f"/api/workspaces/{ws2_id}/cognitive-fabric-node")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_cfn_includes_both_enabled_and_disabled(self, client):
        """Test that list returns both enabled and disabled CFNs"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Create two CFNs
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-enabled", "cfn_name": "enabled-node"},
        )
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-to-disable", "cfn_name": "disabled-node"},
        )

        # Disable one CFN
        disable_response = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-to-disable/disable")
        assert disable_response.status_code == 200

        # List CFNs (should include both enabled and disabled)
        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["nodes"]) == 2

        # Verify both enabled and disabled are present
        cfn_ids = {node["cfn_id"] for node in data["nodes"]}
        assert "cfn-enabled" in cfn_ids
        assert "cfn-to-disable" in cfn_ids

        # Verify enabled status
        for node in data["nodes"]:
            if node["cfn_id"] == "cfn-enabled":
                assert node["enabled"] is True
            elif node["cfn_id"] == "cfn-to-disable":
                assert node["enabled"] is False

    def test_list_cfn_never_includes_deleted(self, client):
        """Test that deleted CFNs are never included in list"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Create three CFNs
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-enabled", "cfn_name": "enabled-node"},
        )
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-disabled", "cfn_name": "disabled-node"},
        )
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-to-delete", "cfn_name": "deleted-node"},
        )

        # Disable one CFN
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled/disable")

        # Disable and delete another CFN
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-to-delete/disable")
        delete_response = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-to-delete")
        assert delete_response.status_code == 204

        # List CFNs (should show enabled + disabled, but not deleted)
        response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        cfn_ids = {node["cfn_id"] for node in data["nodes"]}
        assert "cfn-enabled" in cfn_ids
        assert "cfn-disabled" in cfn_ids
        assert "cfn-to-delete" not in cfn_ids  # Deleted CFN should never appear


class TestCognitiveFabricNodeGet:
    """Test cases for getting Cognitive Fabric Node details"""

    def test_get_cfn_details(self, client, created_cfn):
        """Test getting CFN node details"""
        workspace_id, cfn_id = created_cfn

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

    def test_get_cfn_wrong_workspace(self, client, created_cfn):
        """Test getting CFN from wrong workspace"""
        _, cfn_id = created_cfn

        # Create different workspace
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws2_id = ws2_response.json()["id"]

        # Try to get CFN from wrong workspace
        response = client.get(f"/api/workspaces/{ws2_id}/cognitive-fabric-node/{cfn_id}")
        assert response.status_code == 403


class TestCognitiveFabricNodeUpdate:
    """Test cases for updating Cognitive Fabric Node"""

    def test_update_cfn_name(self, client, created_cfn):
        """Test updating CFN name"""
        workspace_id, cfn_id = created_cfn

        update_data = {"cfn_name": "updated-cfn-name"}

        response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cfn_name"] == "updated-cfn-name"

    def test_update_cfn_config(self, client, created_cfn):
        """Test updating CFN config"""
        workspace_id, cfn_id = created_cfn

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


class TestCognitiveFabricNodeDisable:
    """Test cases for Cognitive Fabric Node disable operation"""

    def test_disable_cfn(self, client, created_cfn):
        """Test disabling CFN node"""
        workspace_id, cfn_id = created_cfn

        response = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["cfn_id"] == cfn_id

        # Verify disabled CFN still appears in list (but with enabled=False)
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["nodes"][0]["cfn_id"] == cfn_id
        assert list_data["nodes"][0]["enabled"] is False

    def test_disable_cfn_twice(self, client, created_cfn):
        """Test disabling CFN twice (should fail second time)"""
        workspace_id, cfn_id = created_cfn

        # First disable
        response1 = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable")
        assert response1.status_code == 200

        # Second disable (should fail - already disabled)
        response2 = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable")
        assert response2.status_code == 400
        assert "already disabled" in response2.json()["detail"]

    def test_disable_cfn_nonexistent(self, client):
        """Test disabling non-existent CFN"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/nonexistent-cfn/disable")
        assert response.status_code == 404


class TestCognitiveFabricNodeDelete:
    """Test cases for Cognitive Fabric Node deregistration (hard delete)"""

    def test_delete_cfn(self, client, created_cfn):
        """Test deregistering CFN node (must disable first)"""
        workspace_id, cfn_id = created_cfn

        # Try to deregister without disabling first (should fail)
        response1 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert response1.status_code == 400
        assert "must be disabled" in response1.json()["detail"]

        # Disable first
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable")

        # Now deregister (should succeed)
        response2 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert response2.status_code == 204

        # Verify CFN no longer appears in list
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        assert list_response.json()["total"] == 0

    def test_delete_cfn_twice(self, client, created_cfn):
        """Test deregistering CFN twice (should fail second time)"""
        workspace_id, cfn_id = created_cfn

        # Disable first
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable")

        # First deregistration
        response1 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert response1.status_code == 204

        # Second deregistration (should fail - not found)
        response2 = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}")
        assert response2.status_code == 404

    def test_delete_cfn_nonexistent(self, client):
        """Test deregistering non-existent CFN"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        response = client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/nonexistent-cfn")
        assert response.status_code == 404

    def test_delete_allows_id_reuse(self, client):
        """Test that deregistered CFN ID can be reused"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-reuse-test", "cfn_name": "test-node-1"}

        # Register CFN
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201

        # Disable CFN
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reuse-test/disable")

        # Deregister CFN
        client.delete(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reuse-test")

        # Register new CFN with same ID (should succeed - ID can be reused)
        new_cfn_data = {"cfn_id": "cfn-reuse-test", "cfn_name": "test-node-2"}
        response2 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=new_cfn_data)
        assert response2.status_code == 201
        assert response2.json()["cfn_name"] == "test-node-2"


class TestCognitiveFabricNodeEnableDisable:
    """Test cases for Cognitive Fabric Node enable/disable operations"""

    def test_disabled_cfn_cannot_auto_reenable(self, client):
        """Test that disabled CFN CANNOT auto re-enable via /register"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Initial creation
        cfn_data = {
            "cfn_id": "cfn-disable-test",
            "cfn_name": "test-node",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201
        assert response1.json()["status"] == "offline"  # Starts offline

        # Disable
        response2 = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disable-test/disable")
        assert response2.status_code == 200

        # Verify disabled CFN still appears in the list (but with enabled=False)
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["nodes"][0]["cfn_id"] == "cfn-disable-test"
        assert list_data["nodes"][0]["enabled"] is False

        # Attempt to re-register (should fail - disabled CFN cannot auto re-enable)
        updated_cfn_data = {
            "cfn_id": "cfn-disable-test",
            "cfn_name": "test-node-updated",
            "cfn_config": {"memory": "8GB"},
        }
        response3 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json=updated_cfn_data,
        )
        assert response3.status_code == 403
        assert "disabled" in response3.json()["detail"].lower()

        # Verify disabled CFN is still in the list with enabled=False
        list_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node")
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["nodes"][0]["cfn_id"] == "cfn-disable-test"
        assert list_data["nodes"][0]["enabled"] is False

    def test_enable_disabled_cfn(self, client):
        """Test manually re-enabling a disabled CFN via /enable endpoint"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Initial creation
        cfn_data = {
            "cfn_id": "cfn-enable-test",
            "cfn_name": "test-node",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201

        # Disable
        response2 = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-enable-test/disable")
        assert response2.status_code == 200

        # Manually re-enable via PATCH /enable
        response3 = client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-enable-test/enable")
        assert response3.status_code == 200
        data = response3.json()
        assert data["enabled"] is True
        assert data["status"] == "offline"  # Offline until heartbeat

        # Now CFN can register and reconnect
        updated_cfn_data = {
            "cfn_id": "cfn-enable-test",
            "cfn_name": "test-node-updated",
            "cfn_config": {"memory": "8GB"},
        }
        response4 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json=updated_cfn_data,
        )
        assert response4.status_code == 201
        assert response4.json()["cfn_name"] == "test-node-updated"

        # Send heartbeat to go online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-enable-test/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_active_cfn_reconnection(self, client):
        """Test active CFN reconnecting (reboot scenario) - should refresh config"""
        # Create workspace
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Initial creation
        cfn_data = {
            "cfn_id": "cfn-reboot-test",
            "cfn_name": "test-node",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201
        assert response1.json()["status"] == "offline"

        # Send heartbeat to go online
        heartbeat1 = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reboot-test/heartbeat")
        assert heartbeat1.status_code == 200
        assert heartbeat1.json()["status"] == "online"

        # Simulate reboot - CFN calls /register again (while still enabled=true, status=online)
        updated_cfn_data = {
            "cfn_id": "cfn-reboot-test",
            "cfn_name": "test-node-rebooted",
            "cfn_config": {"memory": "8GB"},
        }
        response2 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json=updated_cfn_data,
        )
        # Should succeed with 200 OK (refresh), not 403 or 409
        assert response2.status_code == 201  # Currently returns 201 for both new and refresh
        assert response2.json()["cfn_name"] == "test-node-rebooted"
        assert response2.json()["status"] == "offline"  # Back to offline after reboot

        # Send heartbeat again to go back online
        heartbeat2 = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reboot-test/heartbeat")
        assert heartbeat2.status_code == 200
        assert heartbeat2.json()["status"] == "online"

        # Verify updated config
        detail_response = client.get(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-reboot-test")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["cfn_name"] == "test-node-rebooted"
        assert detail["cfn_config"]["memory"] == "8GB"

    def test_active_cfn_name_conflict(self, client):
        """Test active CFN trying to reconnect with a name that conflicts"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        # Register first CFN
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-first", "cfn_name": "first-node"},
        )

        # Register second CFN (online and active)
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-second", "cfn_name": "second-node"},
        )

        # Second CFN tries to reconnect (reboot) with first CFN's name (should fail - name conflict)
        response = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
            json={"cfn_id": "cfn-second", "cfn_name": "first-node"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_disabled_cfn_different_workspace(self, client):
        """Test that disabled CFN cannot register in a different workspace"""
        # Create two workspaces
        ws1_response = client.post("/api/workspaces", json={"name": "Workspace 1"})
        ws2_response = client.post("/api/workspaces", json={"name": "Workspace 2"})
        ws1_id = ws1_response.json()["id"]
        ws2_id = ws2_response.json()["id"]

        # Register CFN in workspace 1
        cfn_data = {"cfn_id": "cfn-workspace-test", "cfn_name": "test-node"}
        response1 = client.post(f"/api/workspaces/{ws1_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201

        # Disable CFN in workspace 1
        client.patch(f"/api/workspaces/{ws1_id}/cognitive-fabric-node/cfn-workspace-test/disable")

        # Try to register in workspace 2 (should fail - CFN is disabled)
        # Note: Disabled check happens before workspace check
        response2 = client.post(
            f"/api/workspaces/{ws2_id}/cognitive-fabric-node", json=cfn_data
        )
        assert response2.status_code == 403
        assert "disabled" in response2.json()["detail"].lower()

    def test_full_enable_disable_cycle(self, client):
        """Test full cycle: register → disable → enable → re-register → heartbeat"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-cycle-test", "cfn_name": "cycle-node"}

        # Create
        client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)

        # Disable
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-cycle-test/disable")

        # Manually enable
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-cycle-test/enable")

        # Re-register (CFN reconnects)
        client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data
        )

        # Send heartbeat (should work now)
        heartbeat_response = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-cycle-test/heartbeat"
        )
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_disabled_cfn_cannot_heartbeat(self, client):
        """Test that a deleted (disabled) CFN cannot send heartbeats"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-disabled-test", "cfn_name": "disabled-node"}

        # Create
        client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)

        # Disable
        client.patch(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled-test/disable")

        # Try to send heartbeat (should fail - disabled)
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled-test/heartbeat")
        assert heartbeat_response.status_code == 403
        assert "disabled" in heartbeat_response.json()["detail"]

        # Try to re-register (should fail - disabled CFN cannot auto re-enable)
        response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

        # Heartbeat still should NOT work
        heartbeat_response2 = client.put(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node/cfn-disabled-test/heartbeat"
        )
        assert heartbeat_response2.status_code == 403

    def test_create_already_active_cfn_refreshes(self, client):
        """Test that registering an already active CFN refreshes config (reboot scenario)"""
        ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
        workspace_id = ws_response.json()["id"]

        cfn_data = {"cfn_id": "cfn-active-test", "cfn_name": "active-node"}

        # Initial creation
        response1 = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response1.status_code == 201

        # Register again (reboot scenario - should refresh config and succeed)
        updated_cfn_data = {
            "cfn_id": "cfn-active-test",
            "cfn_name": "active-node-rebooted",
            "cfn_config": {"memory": "16GB"},
        }
        response2 = client.post(
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=updated_cfn_data
        )
        assert response2.status_code == 201  # Refresh succeeds
        assert response2.json()["cfn_name"] == "active-node-rebooted"
        assert response2.json()["status"] == "offline"  # Back to offline after reboot


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
            f"/api/workspaces/{workspace_id}/cognitive-fabric-node",
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
def created_cfn(client):
    """Fixture: Register a CFN, send heartbeat to make it online, and return workspace_id, cfn_id"""
    ws_response = client.post("/api/workspaces", json={"name": "Test Workspace"})
    workspace_id = ws_response.json()["id"]

    cfn_data = {"cfn_id": "cfn-fixture-123", "cfn_name": "fixture-cfn-node"}

    response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
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
        response = client.post(f"/api/workspaces/{workspace_id}/cognitive-fabric-node", json=cfn_data)
        assert response.status_code == 201

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_data['cfn_id']}/heartbeat")
        assert heartbeat_response.status_code == 200

        cfn_ids.append(cfn_data["cfn_id"])

    return workspace_id, cfn_ids
