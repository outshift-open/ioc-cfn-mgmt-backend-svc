"""
Tests for workspace endpoints in ioc-cfn-mgmt-backend.
"""
import pytest


class TestWorkspaceEndpoints:
    """Test cases for workspace management endpoints."""

    def test_create_workspace_success(self, client, sample_workspace_data):
        """Test successful workspace creation."""
        response = client.post("/api/workspaces", json=sample_workspace_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert isinstance(data["id"], str)
        import uuid

        uuid.UUID(data["id"])

    def test_create_workspace_invalid_data(self, client):
        """Test workspace creation with invalid data."""
        response = client.post("/api/workspaces", json={})
        assert response.status_code == 422

        response = client.post("/api/workspaces", json={"name": ""})
        assert response.status_code == 422

    def test_create_workspace_invalid_json(self, client):
        """Test workspace creation with invalid JSON."""
        response = client.post("/api/workspaces", content="invalid json", headers={"Content-Type": "application/json"})
        assert response.status_code == 422

    def test_list_workspaces_empty(self, client):
        """Test listing workspaces when none exist."""
        response = client.get("/api/workspaces")

        assert response.status_code == 200
        data = response.json()
        assert "workspaces" in data
        assert data["workspaces"] == []

    def test_list_workspaces_with_data(self, client, sample_workspace_data):
        """Test listing workspaces after creating some."""
        create_response = client.post("/api/workspaces", json=sample_workspace_data)
        assert create_response.status_code == 201
        workspace_id = create_response.json()["id"]

        list_response = client.get("/api/workspaces")
        assert list_response.status_code == 200

        data = list_response.json()
        assert "workspaces" in data
        assert len(data["workspaces"]) == 1

        workspace = data["workspaces"][0]
        assert workspace["id"] == workspace_id
        assert workspace["name"] == sample_workspace_data["name"]
        assert "created_at" in workspace

    def test_list_workspaces_multiple(self, client):
        """Test listing multiple workspaces."""
        workspaces_data = [{"name": "Workspace 1"}, {"name": "Workspace 2"}, {"name": "Workspace 3"}]

        created_ids = []
        for ws_data in workspaces_data:
            response = client.post("/api/workspaces", json=ws_data)
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        response = client.get("/api/workspaces")
        assert response.status_code == 200

        data = response.json()
        assert len(data["workspaces"]) == 3

        returned_ids = [ws["id"] for ws in data["workspaces"]]
        for created_id in created_ids:
            assert created_id in returned_ids

    def test_get_workspace_by_id(self, client, created_workspace, sample_workspace_data):
        """Test getting a specific workspace by ID."""
        response = client.get(f"/api/workspaces/{created_workspace}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_workspace
        assert data["name"] == sample_workspace_data["name"]
        assert "created_at" in data

    def test_get_workspace_not_found(self, client):
        """Test getting a workspace that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/workspaces/{fake_id}")

        assert response.status_code == 404

    def test_get_workspace_invalid_id(self, client):
        """Test getting a workspace with invalid ID format."""
        response = client.get("/api/workspaces/invalid-id")

        assert response.status_code == 404

    def test_delete_workspace_blocked_then_succeeds(self, client, sample_workspace_data):
        """Workspace delete should be blocked with dependents, then succeed after cleanup."""
        ws_resp = client.post("/api/workspaces", json=sample_workspace_data)
        assert ws_resp.status_code == 201
        workspace_id = ws_resp.json()["id"]

        mas_data = {
            "name": "WS-Del Test MAS",
            "description": "",
            "agents": {"a1": {"type": "t"}},
            "config": {},
        }
        mas_resp = client.post(f"/api/workspaces/{workspace_id}/multi-agentic-systems", json=mas_data)
        assert mas_resp.status_code == 201
        mas_id = mas_resp.json()["id"]

        # Attempt to delete workspace should be blocked (409) due to dependents
        del_ws_resp_blocked = client.delete(f"/api/workspaces/{workspace_id}")
        assert del_ws_resp_blocked.status_code == 409
        assert "Workspace has dependent objects" in del_ws_resp_blocked.json()["detail"]

        # Delete dependents first
        del_mas_resp = client.delete(f"/api/workspaces/{workspace_id}/multi-agentic-systems/{mas_id}")
        assert del_mas_resp.status_code == 204

        # Workspace delete succeeds
        del_ws_resp_ok = client.delete(f"/api/workspaces/{workspace_id}")
        assert del_ws_resp_ok.status_code == 204

    def test_delete_default_workspace_public_forbidden(self, client):
        """Public delete of Default Workspace should be forbidden (403)."""
        create_resp = client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert create_resp.status_code == 201
        default_ws_id = create_resp.json()["id"]

        # Attempt public delete
        del_resp = client.delete(f"/api/workspaces/{default_ws_id}")
        assert del_resp.status_code == 403
        assert del_resp.json()["detail"] == "Failed to delete workspace: Default Workspace cannot be deleted"

    def test_delete_default_workspace_internal_allowed(self, client):
        """Internal delete of Default Workspace should be allowed (no deps present)."""
        # Create Default Workspace
        create_resp = client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert create_resp.status_code == 201
        default_ws_id = create_resp.json()["id"]

        # Internal delete should succeed
        del_resp = client.delete(f"/api/internal/workspaces/{default_ws_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["message"] in {"Workspace deleted successfully", "Workspace permanently deleted"}

    def test_internal_purge_handles_dependents(self, client):
        """Internal purge should delete dependents and workspace without FK errors."""
        # Create workspace and a MAS dependent
        ws_resp = client.post("/api/workspaces", json={"name": "Default Workspace"})
        assert ws_resp.status_code == 201
        ws_id = ws_resp.json()["id"]

        mas_data = {
            "name": "WS-Purge Test MAS",
            "description": "",
            "agents": {"a1": {"type": "t"}},
            "config": {},
        }
        mas_resp = client.post(f"/api/workspaces/{ws_id}/multi-agentic-systems", json=mas_data)
        assert mas_resp.status_code == 201

        # Internal purge should succeed and remove workspace and dependents
        del_resp = client.delete(f"/api/internal/workspaces/{ws_id}?_purge=true")
        assert del_resp.status_code == 200
        assert del_resp.json()["message"] == "Workspace permanently deleted"
