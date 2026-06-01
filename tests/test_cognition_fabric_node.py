# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for Cognition Fabric Node endpoints

CFN endpoints are global (cross-workspace) resources at /api/cognition-fabric-nodes.
workspace_id is passed in the request body for create, and as a query param for list.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


class TestCognitionFabricNodeCreate:
    """Test cases for Cognition Fabric Node registration"""

    def test_create_cfn_success(self, client):
        """Test successful CFN registration"""
        # First register CFN (without workspace)
        cfn_data = {
            "name": "test-cfn-node",
            "cfn_config": {"memory": "4GB", "max_connections": 100},
            "ip_address": "192.168.1.100",
            "port": 8080,
        }

        response = client.post("/api/cognition-fabric-nodes", json=cfn_data)

        assert response.status_code == 201
        data = response.json()
        cfn_id = data["id"] 
        assert "id" in data
        assert data["name"] == "test-cfn-node"
        assert data["status"] == "offline"  # Starts offline, heartbeat makes it online
        assert "config" in data

        # Verify CFN exists by fetching it (debug check)
        cfn_check = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert cfn_check.status_code == 200, f"CFN check failed: {cfn_check.json()}"

        # Create workspace with CFN association
        ws_response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": cfn_id},
        )
        assert ws_response.status_code == 201, f"Workspace creation failed: {ws_response.json()}"
        workspace_id = ws_response.json()["id"]

        # Verify CFN now has workspace association
        cfn_details = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert cfn_details.status_code == 200
        assert workspace_id in cfn_details.json()["workspace_ids"]

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_create_cfn_duplicate_id(self, client):
        """Test re-registering CFN with same name refreshes config (reconnect scenario)"""
        cfn_data = {"name": "test-cfn-reconnect", "ip_address": "192.168.1.100", "port": 8080}

        # First registration
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Send heartbeat to make it online
        heartbeat = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat.status_code == 200
        assert heartbeat.json()["status"] == "online"

        # Second registration with same name (reconnect scenario - refreshes state)
        response2 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response2.status_code == 201  # Refresh succeeds
        assert response2.json()["id"] == cfn_id  # Same ID returned
        assert response2.json()["status"] == "online"  # Still online after refresh

    def test_create_cfn_duplicate_name_same_workspace(self, client):
        """Test re-registering CFN with duplicate name refreshes the existing node"""
        # First CFN
        response1 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "duplicate-name", "ip_address": "192.168.1.100", "port": 8080},
        )
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Second registration with same name (reconnect scenario)
        response2 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "duplicate-name", "ip_address": "192.168.1.100", "port": 8080},
        )
        assert response2.status_code == 201  # Refresh also returns 201
        assert response2.json()["id"] == cfn_id  # Same ID

    def test_create_cfn_same_name_different_workspaces(self, client):
        """Test re-registering disabled CFN with same name fails with 403"""
        # Register first CFN
        response1 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "shared-name"},
        )
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Create first workspace with CFN
        ws1_response = client.post("/api/workspaces/create", json={"name": "Workspace 1", "cfn_id": cfn_id})
        assert ws1_response.status_code == 201

        # Disable the CFN
        disable_response = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
        assert disable_response.status_code == 200

        # Try to re-register with same name (should fail - disabled)
        response2 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "shared-name"},
        )
        assert response2.status_code == 403  # Forbidden - disabled

    def test_create_cfn_nonexistent_workspace(self, client):
        """Test creating workspace with non-existent CFN"""
        # Try to create workspace with non-existent cfn_id
        response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": "nonexistent-cfn-id"},
        )
        assert response.status_code == 404


class TestCognitionFabricNodeHeartbeat:
    """Test cases for Cognition Fabric Node heartbeat"""

    def test_cfn_heartbeat_success(self, client, created_cfn):
        """Test successful CFN heartbeat"""
        workspace_id, cfn_id = created_cfn

        response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "last_seen" in data

    def test_cfn_heartbeat_after_disable(self, client, created_cfn):
        """Test heartbeat after CFN is disabled (should fail)"""
        workspace_id, cfn_id = created_cfn

        # Disable CFN
        disable_response = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
        assert disable_response.status_code == 200

        # Try heartbeat (should fail)
        response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"]

    def test_cfn_heartbeat_nonexistent_node(self, client):
        """Test heartbeat for non-existent CFN"""
        response = client.put("/api/cognition-fabric-nodes/nonexistent-cfn-id/heartbeat")
        assert response.status_code == 404


class TestCognitionFabricNodeList:
    """Test cases for listing Cognition Fabric Nodes"""

    def test_list_cfn_nodes_empty(self, client):
        """Test listing CFN nodes in empty workspace"""
        # Register CFN first
        cfn_response = client.post("/api/cognition-fabric-nodes", json={"name": "test-node"})
        assert cfn_response.status_code == 201
        cfn_id = cfn_response.json()["id"]

        # Create workspace with CFN
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
        assert ws_response.status_code == 201
        workspace_id = ws_response.json()["id"]

        response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        # Workspace has 1 CFN associated with it now
        assert len(data["nodes"]) == 1
        assert data["total"] == 1
        assert data["nodes"][0]["name"] == "test-node"

    def test_list_cfn_nodes(self, client, multiple_cfn_nodes):
        """Test listing all CFN nodes (global list)"""
        workspace_id, cfn_ids = multiple_cfn_nodes

        response = client.get("/api/cognition-fabric-nodes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 3
        assert data["total"] == 3

        # Verify each node has required fields
        for node in data["nodes"]:
            assert "id" in node
            assert "workspace_ids" in node
            assert "name" in node
            assert "status" in node
            assert "last_seen" in node
            assert "enabled" in node
            assert "created_at" in node

        # Test filtering by workspace - should return only the CFN for that workspace
        response_filtered = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        assert response_filtered.status_code == 200
        filtered_data = response_filtered.json()
        assert len(filtered_data["nodes"]) == 1
        # Check that the first CFN is returned (can't hardcode ID anymore)
        assert filtered_data["nodes"][0]["name"] == "cfn-node-0"

    def test_list_cfn_nodes_with_status_filter(self, client, created_cfn):
        """Test listing CFN nodes with status filter"""
        workspace_id, _ = created_cfn

        # List online nodes
        response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}&status=online")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for node in data["nodes"]:
            assert node["status"] == "online"

    def test_list_cfn_workspace_isolation(self, client):
        """Test CFN nodes are isolated by workspace"""
        # Register CFNs first
        cfn1_response = client.post("/api/cognition-fabric-nodes", json={"name": "cfn-1"})
        cfn2_response = client.post("/api/cognition-fabric-nodes", json={"name": "cfn-2"})
        cfn1_id = cfn1_response.json()["id"]
        cfn2_id = cfn2_response.json()["id"]

        # Create two workspaces with different CFNs
        ws1_response = client.post("/api/workspaces/create", json={"name": "Workspace 1", "cfn_id": cfn1_id})
        ws2_response = client.post("/api/workspaces/create", json={"name": "Workspace 2", "cfn_id": cfn2_id})
        ws1_id = ws1_response.json()["id"]
        ws2_id = ws2_response.json()["id"]

        # List CFN in ws1 should only show cfn-1 (not cfn-2)
        response = client.get(f"/api/cognition-fabric-nodes?workspace_id={ws1_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["nodes"][0]["id"] == cfn1_id

        # List CFN in ws2 should only show cfn-2 (not cfn-1)
        response = client.get(f"/api/cognition-fabric-nodes?workspace_id={ws2_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["nodes"][0]["id"] == cfn2_id

    def test_list_cfn_includes_both_enabled_and_disabled(self, client):
        """Test that list returns both enabled and disabled CFNs"""
        # Create two CFNs first
        cfn1_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "enabled-node"},
        )
        cfn2_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "disabled-node"},
        )
        cfn1_id = cfn1_response.json()["id"]
        cfn2_id = cfn2_response.json()["id"]

        # Create workspace with first CFN only
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn1_id})
        assert ws_response.status_code == 201
        workspace_id = ws_response.json()["id"]

        # Disable second CFN (not associated with workspace)
        disable_response = client.patch(f"/api/cognition-fabric-nodes/{cfn2_id}/disable")
        assert disable_response.status_code == 200

        # List CFNs (should show only cfn-enabled because cfn-to-disable is not associated with this workspace)
        response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["nodes"]) == 1

        # Verify only enabled node is present (cfn-to-disable is not associated with this workspace)
        cfn_ids = {node["id"] for node in data["nodes"]}
        assert cfn1_id in cfn_ids
        assert cfn2_id not in cfn_ids

    def test_list_cfn_never_includes_deleted(self, client):
        """Test that deleted CFNs are never included in list"""
        # Create three CFNs first
        cfn1_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "enabled-node"},
        )
        cfn2_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "disabled-node"},
        )
        cfn3_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "deleted-node"},
        )
        cfn1_id = cfn1_response.json()["id"]
        cfn2_id = cfn2_response.json()["id"]
        cfn3_id = cfn3_response.json()["id"]

        # Create workspace with first CFN only
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn1_id})
        assert ws_response.status_code == 201
        workspace_id = ws_response.json()["id"]

        # Disable one CFN (not associated with workspace)
        client.patch(f"/api/cognition-fabric-nodes/{cfn2_id}/disable")

        # Disable and delete another CFN (not associated with workspace)
        client.patch(f"/api/cognition-fabric-nodes/{cfn3_id}/disable")
        delete_response = client.delete(f"/api/cognition-fabric-nodes/{cfn3_id}")
        assert delete_response.status_code == 204

        # List CFNs (should only show cfn-enabled because others are not associated with this workspace)
        response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        cfn_ids = {node["id"] for node in data["nodes"]}
        assert cfn1_id in cfn_ids
        assert cfn2_id not in cfn_ids  # Not associated with workspace
        assert cfn3_id not in cfn_ids  # Not associated with workspace


class TestCognitionFabricNodeGet:
    """Test cases for getting Cognition Fabric Node details"""

    def test_get_cfn_details(self, client, created_cfn):
        """Test getting CFN node details"""
        workspace_id, cfn_id = created_cfn

        response = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == cfn_id
        assert workspace_id in data["workspace_ids"]
        assert "name" in data
        assert "config" in data
        assert "workspaces" in data["config"]
        assert "memory_providers" in data["config"]
        assert "status" in data
        assert "last_seen" in data
        assert "enabled" in data
        assert "created_at" in data

    def test_get_cfn_nonexistent(self, client):
        """Test getting non-existent CFN"""
        response = client.get("/api/cognition-fabric-nodes/nonexistent-cfn")
        assert response.status_code == 404

    def test_get_cfn_shows_workspace_association(self, client, created_cfn):
        """Test getting CFN shows correct workspace association"""
        workspace_id, cfn_id = created_cfn

        # Create different workspace with a different CFN
        # First register CFN for workspace 2
        cfn2_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "ws2-cfn-node"},
        )
        assert cfn2_response.status_code == 201
        cfn2_id = cfn2_response.json()["id"]

        ws2_response = client.post("/api/workspaces/create", json={"name": "Workspace 2", "cfn_id": cfn2_id})
        assert ws2_response.status_code == 201
        ws2_id = ws2_response.json()["id"]

        # Get CFN - should only be associated with original workspace
        response = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert response.status_code == 200
        data = response.json()
        assert workspace_id in data["workspace_ids"]
        assert ws2_id not in data["workspace_ids"]


class TestCognitionFabricNodeUpdate:
    """Test cases for updating Cognition Fabric Node"""

    def test_update_cfn_name(self, client, created_cfn):
        """Test updating CFN name"""
        workspace_id, cfn_id = created_cfn

        update_data = {"name": "updated-cfn-name"}

        response = client.put(
            f"/api/cognition-fabric-nodes/{cfn_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-cfn-name"

    def test_update_cfn_config(self, client, created_cfn):
        """Test updating CFN config"""
        workspace_id, cfn_id = created_cfn

        update_data = {"cfn_config": {"memory": "8GB", "max_connections": 200}}

        response = client.put(
            f"/api/cognition-fabric-nodes/{cfn_id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        # Config structure has been updated - verify response is successful
        assert "config" in data
        assert "workspaces" in data["config"]
        assert "memory_providers" in data["config"]

    def test_update_cfn_duplicate_name(self, client, multiple_cfn_nodes):
        """Test updating CFN with duplicate name"""
        workspace_id, cfn_ids = multiple_cfn_nodes

        # First get the name of cfn_ids[1]
        get_response = client.get(f"/api/cognition-fabric-nodes/{cfn_ids[1]}")
        existing_name = get_response.json()["name"]

        # Try to update cfn_ids[0] with that name
        response = client.put(
            f"/api/cognition-fabric-nodes/{cfn_ids[0]}",
            json={"name": existing_name},
        )
        assert response.status_code == 409

    def test_update_cfn_nonexistent(self, client):
        """Test updating non-existent CFN"""
        response = client.put(
            "/api/cognition-fabric-nodes/nonexistent-cfn",
            json={"name": "new-name"},
        )
        assert response.status_code == 404


class TestCognitionFabricNodeDisable:
    """Test cases for Cognition Fabric Node disable operation"""

    def test_disable_cfn(self, client, created_cfn):
        """Test disabling CFN node"""
        workspace_id, cfn_id = created_cfn

        response = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["id"] == cfn_id

        # Verify disabled CFN still appears in list (but with enabled=False)
        list_response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["nodes"][0]["id"] == cfn_id
        assert list_data["nodes"][0]["enabled"] is False

    def test_disable_cfn_twice(self, client, created_cfn):
        """Test disabling CFN twice (should fail second time)"""
        workspace_id, cfn_id = created_cfn

        # First disable
        response1 = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
        assert response1.status_code == 200

        # Second disable (should fail - already disabled)
        response2 = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
        assert response2.status_code == 400
        assert "already disabled" in response2.json()["detail"]

    def test_disable_cfn_nonexistent(self, client):
        """Test disabling non-existent CFN"""
        response = client.patch("/api/cognition-fabric-nodes/nonexistent-cfn/disable")
        assert response.status_code == 404


class TestCognitionFabricNodeDelete:
    """Test cases for Cognition Fabric Node deregistration (hard delete)"""

    def test_delete_cfn(self, client, created_cfn):
        """Test deregistering CFN node (must disable first)"""
        workspace_id, cfn_id = created_cfn

        # Try to deregister without disabling first (should fail)
        response1 = client.delete(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert response1.status_code == 400
        assert "must be disabled" in response1.json()["detail"]

        # Disable first
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        # Now deregister (should succeed)
        response2 = client.delete(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert response2.status_code == 204

        # Verify CFN no longer appears in list
        list_response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        assert list_response.json()["total"] == 0

    def test_delete_cfn_twice(self, client, created_cfn):
        """Test deregistering CFN twice (should fail second time)"""
        workspace_id, cfn_id = created_cfn

        # Disable first
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        # First deregistration
        response1 = client.delete(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert response1.status_code == 204

        # Second deregistration (should fail - not found)
        response2 = client.delete(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert response2.status_code == 404

    def test_delete_cfn_nonexistent(self, client):
        """Test deregistering non-existent CFN"""
        response = client.delete("/api/cognition-fabric-nodes/nonexistent-cfn")
        assert response.status_code == 404

    def test_delete_allows_id_reuse(self, client):
        """Test that deregistered CFN name can be reused after deletion"""
        cfn_data = {"name": "test-node-1", "ip_address": "192.168.1.100", "port": 8080}

        # Register CFN
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Create workspace with CFN
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
        assert ws_response.status_code == 201

        # Disable CFN
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        # Deregister CFN
        client.delete(f"/api/cognition-fabric-nodes/{cfn_id}")

        # Register new CFN with same name (should succeed - name can be reused after deletion)
        new_cfn_data = {"name": "test-node-1", "ip_address": "192.168.1.100", "port": 8080}
        response2 = client.post("/api/cognition-fabric-nodes", json=new_cfn_data)
        assert response2.status_code == 201
        assert response2.json()["name"] == "test-node-1"


class TestCognitionFabricNodeEnableDisable:
    """Test cases for Cognition Fabric Node enable/disable operations"""

    def test_disabled_cfn_cannot_auto_reenable(self, client):
        """Test that disabled CFN CANNOT auto re-enable via /register"""
        # Initial creation
        cfn_data = {
            "name": "test-node-disable",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        assert response1.json()["status"] == "offline"  # Starts offline
        cfn_id = response1.json()["id"]

        # Create workspace with CFN
        ws_response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": cfn_id},
        )
        assert ws_response.status_code == 201
        workspace_id = ws_response.json()["id"]

        # Disable
        response2 = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
        assert response2.status_code == 200

        # Verify disabled CFN still appears in the list (but with enabled=False)
        list_response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["nodes"][0]["id"] == cfn_id
        assert list_data["nodes"][0]["enabled"] is False

        # Attempt to re-register with same name (should fail - disabled CFN cannot auto re-enable)
        updated_cfn_data = {
            "name": "test-node-disable",
            "cfn_config": {"memory": "8GB"},
        }
        response3 = client.post("/api/cognition-fabric-nodes", json=updated_cfn_data)
        assert response3.status_code == 403
        assert "disabled" in response3.json()["detail"].lower()

        # Verify disabled CFN is still in the list with enabled=False
        list_response = client.get(f"/api/cognition-fabric-nodes?workspace_id={workspace_id}")
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["nodes"][0]["id"] == cfn_id
        assert list_data["nodes"][0]["enabled"] is False

    def test_enable_disabled_cfn(self, client):
        """Test manually re-enabling a disabled CFN via /enable endpoint"""
        # Initial creation
        cfn_data = {
            "name": "test-node-enable",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Create workspace with CFN
        ws_response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": cfn_id},
        )
        assert ws_response.status_code == 201

        # Disable
        response2 = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
        assert response2.status_code == 200

        # Manually re-enable via PATCH /enable
        response3 = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/enable")
        assert response3.status_code == 200
        data = response3.json()
        assert data["enabled"] is True
        assert data["status"] == "offline"  # Offline until heartbeat

        # Register again with same name (reboot scenario - should refresh config and succeed)
        updated_cfn_data = {
            "name": "test-node-enable",
            "cfn_config": {"memory": "8GB"},
        }
        response4 = client.post("/api/cognition-fabric-nodes", json=updated_cfn_data)
        assert response4.status_code == 201  # Refresh also returns 201
        assert response4.json()["id"] == cfn_id  # Same ID

        # Send heartbeat to go online
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_active_cfn_reconnection(self, client):
        """Test active CFN reconnecting (reboot scenario) - should refresh config"""
        # Initial creation
        cfn_data = {
            "name": "test-node-reboot",
            "cfn_config": {"memory": "4GB"},
        }
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        assert response1.json()["status"] == "offline"
        cfn_id = response1.json()["id"]

        # Create workspace with CFN
        ws_response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": cfn_id},
        )
        assert ws_response.status_code == 201

        # Send heartbeat to go online
        heartbeat1 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat1.status_code == 200
        assert heartbeat1.json()["status"] == "online"

        # Simulate reboot - CFN calls /register again with same name (while still enabled=true, status=online)
        updated_cfn_data = {
            "name": "test-node-reboot",
            "cfn_config": {"memory": "8GB"},
        }
        response2 = client.post("/api/cognition-fabric-nodes", json=updated_cfn_data)
        # Should succeed with 201 (refresh)
        assert response2.status_code == 201
        assert response2.json()["id"] == cfn_id  # Same ID
        assert response2.json()["status"] == "online"  # Still online after refresh

        # Send heartbeat again
        heartbeat2 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat2.status_code == 200
        assert heartbeat2.json()["status"] == "online"

        # Verify updated config
        detail_response = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["name"] == "test-node-reboot"
        # Config structure has been updated - verify workspaces and memory_providers exist
        assert "workspaces" in detail["config"]
        assert "memory_providers" in detail["config"]

    def test_active_cfn_name_conflict(self, client):
        """Test active CFN trying to reconnect with a name that conflicts"""
        # Register first CFN
        response1 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "first-node"},
        )
        cfn1_id = response1.json()["id"]

        # Register second CFN (online and active)
        response2 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "second-node"},
        )

        # Create workspace with first CFN
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn1_id})
        assert ws_response.status_code == 201

        # Second CFN tries to reconnect with first CFN's name (should refresh the first one)
        response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "first-node"},
        )
        assert response.status_code == 201  # Refresh the existing first-node
        assert response.json()["id"] == cfn1_id

    def test_disabled_cfn_different_workspace(self, client):
        """Test that disabled CFN cannot re-register with same name"""
        # Register CFN
        cfn_data = {"name": "test-node-ws", "ip_address": "192.168.1.100", "port": 8080}
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Create workspace with CFN
        ws1_response = client.post(
            "/api/workspaces/create",
            json={"name": "Workspace 1", "cfn_id": cfn_id}
        )
        assert ws1_response.status_code == 201

        # Disable CFN
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        # Try to re-register with same name (should fail - CFN is disabled)
        response2 = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "test-node-ws"},
        )
        assert response2.status_code == 403
        assert "disabled" in response2.json()["detail"].lower()

    def test_full_enable_disable_cycle(self, client):
        """Test full cycle: register → disable → enable → re-register → heartbeat"""
        cfn_data = {"name": "cycle-node", "ip_address": "192.168.1.100", "port": 8080}

        # Create
        response = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        cfn_id = response.json()["id"]

        # Create workspace with CFN
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
        assert ws_response.status_code == 201

        # Disable
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        # Manually enable
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/enable")

        # Re-register with same name (CFN reconnects)
        client.post("/api/cognition-fabric-nodes", json=cfn_data)

        # Send heartbeat (should work now)
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

    def test_disabled_cfn_cannot_heartbeat(self, client):
        """Test that a disabled CFN cannot send heartbeats"""
        cfn_data = {"name": "disabled-node", "ip_address": "192.168.1.100", "port": 8080}

        # Create
        response = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        cfn_id = response.json()["id"]

        # Create workspace with CFN
        ws_response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": cfn_id}
        )
        assert ws_response.status_code == 201

        # Disable
        client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")

        # Try to send heartbeat (should fail - disabled)
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 403
        assert "disabled" in heartbeat_response.json()["detail"]

        # Try to re-register with same name (should fail - disabled CFN cannot auto re-enable)
        response = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

        # Heartbeat still should NOT work
        heartbeat_response2 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response2.status_code == 403

    def test_create_already_active_cfn_refreshes(self, client):
        """Test that registering an already active CFN refreshes config (reboot scenario)"""
        cfn_data = {"name": "active-node", "ip_address": "192.168.1.100", "port": 8080}

        # Initial creation
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Create workspace with CFN
        ws_response = client.post(
            "/api/workspaces/create",
            json={"name": "Test Workspace", "cfn_id": cfn_id}
        )
        assert ws_response.status_code == 201

        # Register again with same name (reboot scenario - should refresh config and succeed)
        updated_cfn_data = {
            "name": "active-node",
            "cfn_config": {"memory": "16GB"},
        }
        response2 = client.post("/api/cognition-fabric-nodes", json=updated_cfn_data)
        assert response2.status_code == 201  # Refresh succeeds
        assert response2.json()["id"] == cfn_id  # Same ID
        assert response2.json()["status"] == "offline"  # Offline until heartbeat


class TestCognitionFabricNodeBackgroundMonitoring:
    """Test cases for CFN background monitoring (marking stale nodes offline)"""

    def test_mark_stale_nodes_offline(self, client):
        """Test that stale nodes are marked offline"""
        # This test would require mocking time or waiting
        # For now, we'll test the service method directly
        from server.services.cognition_fabric_node import cognition_fabric_node_service

        # Register CFN
        register_response = client.post(
            "/api/cognition-fabric-nodes",
            json={"name": "stale-node"},
        )
        assert register_response.status_code == 201
        assert register_response.json()["status"] == "offline"  # Starts offline
        cfn_id = register_response.json()["id"]

        # Create workspace and register CFN
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
        assert ws_response.status_code == 201

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 200
        assert heartbeat_response.json()["status"] == "online"

        # Manually call mark_stale_nodes_offline with 0 minute threshold
        # (should mark the online node as offline immediately since last_seen is in the past)
        count = cognition_fabric_node_service.mark_stale_nodes_offline(threshold_minutes=0)

        # Should mark at least one node as offline
        assert count >= 1

        # Verify node is offline
        response = client.get(f"/api/cognition-fabric-nodes/{cfn_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "offline"


class TestCognitionFabricNodeConfigVersion:
    """Test cases for config_version functionality"""

    def test_config_version_returned_in_heartbeat(self, client, created_cfn):
        """Test that config_version is returned in heartbeat response"""
        workspace_id, cfn_id = created_cfn

        # Send heartbeat
        response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert "config_version" in data
        assert isinstance(data["config_version"], int)
        assert data["config_version"] >= 0

    def test_config_version_unchanged_on_heartbeat(self, client, created_cfn):
        """Test that config_version remains unchanged across heartbeats when config doesn't change"""
        workspace_id, cfn_id = created_cfn

        # Send first heartbeat and get config_version
        response1 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert response1.status_code == 200
        config_version_1 = response1.json()["config_version"]

        # Send second heartbeat
        response2 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert response2.status_code == 200
        config_version_2 = response2.json()["config_version"]

        # config_version should remain the same (config hasn't changed)
        assert config_version_1 == config_version_2

    def test_config_version_incremented_on_config_change(self, client, created_cfn):
        """Test that config_version increments when CFN config changes"""
        workspace_id, cfn_id = created_cfn

        # Get initial config_version via heartbeat
        response1 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert response1.status_code == 200
        initial_version = response1.json()["config_version"]

        # Update CFN config (triggers config regeneration and version increment)
        update_response = client.put(
            f"/api/cognition-fabric-nodes/{cfn_id}",
            json={"cfn_config": {"memory": "16GB", "new_setting": "value"}},
        )
        assert update_response.status_code == 200

        # Send heartbeat again
        response2 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert response2.status_code == 200
        updated_version = response2.json()["config_version"]

        # config_version should have incremented
        assert updated_version > initial_version

    def test_config_version_incremented_on_cfn_refresh(self, client):
        """Test that config_version increments when CFN reconnects (refresh scenario)"""
        # Create initial CFN
        cfn_data = {"name": "refresh-test-node", "cfn_config": {"version": "1.0"}}
        response1 = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response1.status_code == 201
        cfn_id = response1.json()["id"]

        # Create workspace
        ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
        assert ws_response.status_code == 201

        # Send heartbeat and get initial config_version
        heartbeat1 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat1.status_code == 200
        initial_version = heartbeat1.json()["config_version"]

        # Reconnect with same name (refresh scenario)
        refreshed_cfn_data = {"name": "refresh-test-node", "cfn_config": {"version": "2.0"}}
        response2 = client.post("/api/cognition-fabric-nodes", json=refreshed_cfn_data)
        assert response2.status_code == 201
        assert response2.json()["id"] == cfn_id  # Same ID

        # Send heartbeat and get new config_version
        heartbeat2 = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat2.status_code == 200
        refreshed_version = heartbeat2.json()["config_version"]

        # config_version should have incremented
        assert refreshed_version > initial_version

    def test_config_version_in_registration_response(self, client):
        """Test that config_version is present in registration config response"""
        # Register CFN
        cfn_data = {"name": "version-test-node", "cfn_config": {"version": "1.0"}}
        register_response = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert register_response.status_code == 201
        cfn_id = register_response.json()["id"]

        # Get config_version from registration response (embedded in config)
        registration_config = register_response.json()["config"]
        assert "config_version" in registration_config
        assert isinstance(registration_config["config_version"], int)

        # Send heartbeat to get config_version as top-level field
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 200
        heartbeat_version = heartbeat_response.json()["config_version"]

        # Both should be the same version (no config changes between registration and heartbeat)
        assert registration_config["config_version"] == heartbeat_version


class TestCFNConfigCognitionEngines:
    """cognition_engines appear in CFN config payload with auth decrypted."""

    _AUTH = {"type": "api_key", "credentials": {"api_key": "secret-key"}}

    def _register_ce(self, client, cfn_id, name="test-ce"):
        resp = client.post(
            "/api/cognition-engines",
            json={
                "cfn_id": cfn_id,
                "name": name,
                "url": "http://ce.internal:9004",
                "version": "1.0.0",
                "type": "custom",
                "auth": self._AUTH,
            },
        )
        assert resp.status_code == 201
        return resp.json()["ce_id"]

    def test_workspaces_config_includes_cognition_engines(self, client, created_cfn):
        """GET /cognitive-fabric-node/{id}/workspaces includes cognition_engines at top level."""
        _, cfn_id = created_cfn
        self._register_ce(client, cfn_id)

        resp = client.get(f"/api/cognitive-fabric-node/{cfn_id}/workspaces")
        assert resp.status_code == 200
        assert "cognition_engines" in resp.json()

    def test_workspaces_config_ce_auth_is_decrypted(self, client, created_cfn):
        """auth.credentials is decrypted in the config payload."""
        _, cfn_id = created_cfn
        self._register_ce(client, cfn_id)

        engines = client.get(f"/api/cognitive-fabric-node/{cfn_id}/workspaces").json()["cognition_engines"]
        assert len(engines) == 1
        auth = engines[0]["auth"]
        assert auth["credentials"]["api_key"] == "secret-key"
        assert "credentials_encrypted" not in auth

    def test_workspaces_config_ce_fields_present(self, client, created_cfn):
        """CE entry in config payload includes all expected fields."""
        _, cfn_id = created_cfn
        self._register_ce(client, cfn_id)

        engine = client.get(f"/api/cognitive-fabric-node/{cfn_id}/workspaces").json()["cognition_engines"][0]
        for field in ("id", "name", "url", "type", "enabled", "status", "capabilities", "metrics", "config", "mas_config", "auth"):
            assert field in engine

    def test_workspaces_config_no_ce_when_none_registered(self, client, created_cfn):
        """cognition_engines is empty when no CEs are registered for this CFN."""
        _, cfn_id = created_cfn

        engines = client.get(f"/api/cognitive-fabric-node/{cfn_id}/workspaces").json()["cognition_engines"]
        assert engines == []

    def test_workspaces_config_ce_scoped_to_cfn(self, client, created_cfn):
        """CEs from another CFN do not appear in this CFN's config."""
        _, cfn_id = created_cfn

        other_cfn_id = client.post(
            "/api/cognition-fabric-nodes/register",
            json={"name": "other-cfn"},
        ).json()["id"]
        self._register_ce(client, other_cfn_id, name="other-ce")

        engines = client.get(f"/api/cognitive-fabric-node/{cfn_id}/workspaces").json()["cognition_engines"]
        assert engines == []

    def test_get_cfn_detail_config_includes_cognition_engines(self, client, created_cfn):
        """GET /cognition-fabric-nodes/{id} config field includes cognition_engines."""
        _, cfn_id = created_cfn
        self._register_ce(client, cfn_id)

        detail = client.get(f"/api/cognition-fabric-nodes/{cfn_id}").json()
        assert "cognition_engines" in detail["config"]
        assert len(detail["config"]["cognition_engines"]) == 1


# Pytest fixtures


@pytest.fixture
def created_cfn(client):
    """Fixture: Register a CFN, send heartbeat to make it online, and return workspace_id, cfn_id"""
    cfn_data = {"name": "fixture-cfn-node", "ip_address": "192.168.1.100", "port": 8080}

    response = client.post("/api/cognition-fabric-nodes", json=cfn_data)
    assert response.status_code == 201
    assert response.json()["status"] == "offline"  # Initially offline
    cfn_id = response.json()["id"]

    # Create workspace with CFN
    ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
    assert ws_response.status_code == 201
    workspace_id = ws_response.json()["id"]

    # Send heartbeat to make it online
    heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["status"] == "online"  # Now online

    return workspace_id, cfn_id


@pytest.fixture
def multiple_cfn_nodes(client):
    """Fixture: Register multiple CFN nodes, send heartbeats to make them online, and return workspace_id, [cfn_ids]"""
    # Register first CFN
    cfn_data_0 = {"name": "cfn-node-0", "ip_address": "192.168.1.100", "port": 8080}
    response = client.post("/api/cognition-fabric-nodes", json=cfn_data_0)
    assert response.status_code == 201
    cfn_id_0 = response.json()["id"]

    # Create workspace with first CFN
    ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id_0})
    assert ws_response.status_code == 201
    workspace_id = ws_response.json()["id"]

    # Send heartbeat for first CFN
    heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id_0}/heartbeat")
    assert heartbeat_response.status_code == 200

    cfn_ids = [cfn_id_0]

    # Register remaining CFNs and create additional workspaces for them
    for i in range(1, 3):
        cfn_data = {"name": f"cfn-node-{i}", "ip_address": "192.168.1.100", "port": 8080 + i}
        response = client.post("/api/cognition-fabric-nodes", json=cfn_data)
        assert response.status_code == 201
        cfn_id = response.json()["id"]

        # Create additional workspace with this CFN (each workspace associated with a different CFN)
        ws_resp = client.post(
            "/api/workspaces/create",
            json={"name": f"Test Workspace {i}", "cfn_id": cfn_id}
        )
        assert ws_resp.status_code == 201

        # Send heartbeat to make it online
        heartbeat_response = client.put(f"/api/cognition-fabric-nodes/{cfn_id}/heartbeat")
        assert heartbeat_response.status_code == 200

        cfn_ids.append(cfn_id)

    return workspace_id, cfn_ids
