"""
Tests for Knowledge Adapter endpoints in ioc-cfn-mgmt-backend.
"""
import pytest


class TestKnowledgeAdapterEndpoints:
    """Test cases for Knowledge Adapter management endpoints."""

    @pytest.fixture
    def created_mas(self, client, created_workspace):
        """Create a MAS and return its ID."""
        mas_data = {
            "name": "Test MAS for KEP",
            "description": "MAS for KEP testing",
            "agents": {"agent1": {"type": "test"}},
            "config": {},
        }
        response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas_data)
        assert response.status_code == 201
        return response.json()["id"]

    def test_create_kep_info_extraction_success(self, client, created_workspace, created_mas):
        """Test successful KEP creation with info-extraction software type."""
        kep_data = {
            "name": "Test Info Extraction KEP",
            "mas_ids": [created_mas],
            "type": "pull",
            "software_type": "info-extraction",
            "software_config": {"entities": ["PERSON", "ORG"], "confidence_threshold": 0.8},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Info Extraction KEP"
        assert isinstance(data["id"], str)

        import uuid

        uuid.UUID(data["id"])

    def test_create_kep_otel_success(self, client, created_workspace, created_mas):
        """Test successful KEP creation with otel software type."""
        kep_data = {
            "name": "Test OTEL KEP",
            "mas_ids": [created_mas],
            "type": "push",
            "software_type": "otel",
            "software_config": {"resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": []}]},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test OTEL KEP"

    def test_create_kep_invalid_software_type(self, client, created_workspace, created_mas):
        """Test creating KEP with invalid software type."""
        kep_data = {
            "name": "Test Invalid KEP",
            "mas_ids": [created_mas],
            "type": "pull",
            "software_type": "invalid-type",
            "software_config": {},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 404
        assert "Software template 'invalid-type' not found" in response.json()["detail"]

    def test_create_kep_workspace_not_found(self, client, created_mas):
        """Test creating KEP in non-existent workspace."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"
        kep_data = {
            "name": "Test KEP",
            "mas_ids": [created_mas],
            "type": "pull",
            "software_type": "info-extraction",
            "software_config": {},
        }

        response = client.post(f"/api/workspaces/{fake_workspace_id}/knowledge-adapters", json=kep_data)

        assert response.status_code == 404

    def test_create_kep_invalid_mas_id(self, client, created_workspace):
        """Test creating KEP with non-existent MAS ID."""
        fake_mas_id = "00000000-0000-0000-0000-000000000000"
        kep_data = {
            "name": "Test KEP",
            "mas_ids": [fake_mas_id],
            "type": "pull",
            "software_type": "info-extraction",
            "software_config": {},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 404
        assert "Multi-agentic system with id" in response.json()["detail"]

    def test_create_kep_missing_required_fields(self, client, created_workspace):
        """Test creating KEP with missing required fields."""
        kep_data = {"name": "Incomplete KEP"}

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 422

    def test_create_kep_invalid_type(self, client, created_workspace, created_mas):
        """Test creating KEP with invalid type field."""
        kep_data = {
            "name": "Test KEP",
            "mas_ids": [created_mas],
            "type": "invalid-type",
            "software_type": "info-extraction",
            "software_config": {},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 422

    def test_create_kep_multiple_mas_ids(self, client, created_workspace):
        """Test creating KEP with multiple MAS IDs."""
        # Create two MAS
        mas1_data = {"name": "MAS 1", "description": "First MAS", "agents": {"agent1": {"type": "test"}}, "config": {}}
        mas2_data = {"name": "MAS 2", "description": "Second MAS", "agents": {"agent2": {"type": "test"}}, "config": {}}

        mas1_response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas1_data)
        mas2_response = client.post(f"/api/workspaces/{created_workspace}/multi-agentic-systems", json=mas2_data)

        mas1_id = mas1_response.json()["id"]
        mas2_id = mas2_response.json()["id"]

        kep_data = {
            "name": "Multi-MAS KEP",
            "mas_ids": [mas1_id, mas2_id],
            "type": "pull",
            "software_type": "info-extraction",
            "software_config": {"entities": ["PERSON"]},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Multi-MAS KEP"

    def test_list_kep_empty(self, client, created_workspace):
        """Test listing KEP when none exist."""
        response = client.get(f"/api/workspaces/{created_workspace}/knowledge-adapters")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data["knowledge_adapters"]) == 0

    def test_list_kep_with_data(self, client, created_workspace, created_mas):
        """Test listing KEP with existing data."""
        kep_data = {
            "name": "Test KEP 1",
            "mas_ids": [created_mas],
            "type": "pull",
            "software_type": "info-extraction",
            "software_config": {"entities": ["PERSON"]},
        }

        create_response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)
        assert create_response.status_code == 201

        # List KEPs
        response = client.get(f"/api/workspaces/{created_workspace}/knowledge-adapters")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data["knowledge_adapters"]) == 1

        kep = data["knowledge_adapters"][0]
        assert kep["name"] == "Test KEP 1"
        assert kep["mas_ids"] == [created_mas]
        assert kep["type"] == "pull"
        assert kep["software_type"] == "info-extraction"
        assert kep["software_config"] == {"entities": ["PERSON"]}
        assert "id" in kep
        assert "created_at" in kep
        assert "updated_at" in kep

    def test_list_kep_workspace_not_found(self, client):
        """Test listing KEP in non-existent workspace."""
        fake_workspace_id = "00000000-0000-0000-0000-000000000000"

        response = client.get(f"/api/workspaces/{fake_workspace_id}/knowledge-adapters")

        assert response.status_code == 404

    def test_create_kep_empty_mas_ids_list(self, client, created_workspace):
        """Test creating KEP with empty mas_ids list."""
        kep_data = {
            "name": "Empty MAS KEP",
            "mas_ids": [],
            "type": "pull",
            "software_type": "info-extraction",
            "software_config": {},
        }

        response = client.post(f"/api/workspaces/{created_workspace}/knowledge-adapters", json=kep_data)

        assert response.status_code == 422
