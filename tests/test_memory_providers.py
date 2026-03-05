"""Tests for Memory Provider API endpoints"""

import pytest
from fastapi import status


class TestMemoryProviderCreate:
    """Test memory provider creation with different auth types"""

    def test_create_memory_provider_no_auth(self, client):
        """Test creating memory provider with no authentication"""
        payload = {
            "memory_provider_name": "default-memory-service",
            "description": "Default memory service for general-purpose storage. Supports embeddings, vector search, and conversation history queries.",
            "config": {
                "url": "http://localhost:8765",
                "shared": False,
                "auth": {"type": "none"},
            },
        }

        response = client.post("/api/memory-providers", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["memory_provider_name"] == "default-memory-service"
        assert data["config"]["url"] == "http://localhost:8765"
        assert data["config"]["auth"]["type"] == "none"
        assert data["enabled"] is True
        assert "memory_provider_id" in data

    def test_create_memory_provider_token_auth_mem0(self, client):
        """Test creating memory provider with token auth (Mem0 style)"""
        payload = {
            "memory_provider_name": "mem0-memory-service",
            "description": "Mem0 memory service for personalized agent memory. Supports user preference queries, contextual retrieval, and long-term memory storage.",
            "config": {
                "url": "https://api.mem0.ai",
                "shared": False,
                "auth": {
                    "type": "token",
                    "credentials": {"api_key": "m0-test-key-abc123"},
                },
            },
        }

        response = client.post("/api/memory-providers", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["memory_provider_name"] == "mem0-memory-service"
        assert data["config"]["auth"]["type"] == "token"
        # Credentials should be encrypted
        assert data["config"]["auth"]["credentials"]["api_key"] == "***ENCRYPTED***"

    def test_create_memory_provider_bearer_auth(self, client):
        """Test creating memory provider with bearer token auth"""
        payload = {
            "memory_provider_name": "oauth-memory-service",
            "description": "OAuth-protected memory service",
            "config": {
                "url": "https://memory.example.com:9003",
                "shared": True,
                "auth": {
                    "type": "bearer",
                    "credentials": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test",
                    },
                },
            },
        }

        response = client.post("/api/memory-providers", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["config"]["auth"]["type"] == "bearer"
        assert data["config"]["auth"]["credentials"]["access_token"] == "***ENCRYPTED***"

    def test_create_memory_provider_basic_auth(self, client):
        """Test creating memory provider with basic authentication"""
        payload = {
            "memory_provider_name": "grafiti-selfhosted",
            "description": "Self-hosted Grafiti instance for internal knowledge graphs. Supports complex entity queries and relationship mapping.",
            "config": {
                "url": "https://grafiti.internal.company.com:8443",
                "shared": True,
                "auth": {
                    "type": "basic",
                    "credentials": {"username": "admin", "password": "securepass123"},
                },
            },
        }

        response = client.post("/api/memory-providers", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["config"]["auth"]["type"] == "basic"
        assert data["config"]["auth"]["credentials"]["password"] == "***ENCRYPTED***"

    def test_create_memory_provider_custom_header_auth(self, client):
        """Test creating memory provider with custom header authentication"""
        payload = {
            "memory_provider_name": "custom-memory-provider",
            "description": "Custom memory service with proprietary auth",
            "config": {
                "url": "https://memory.custom.io",
                "shared": False,
                "auth": {
                    "type": "custom",
                    "credentials": {
                        "header_name": "X-API-Token",
                        "header_value": "custom-token-abc123",
                    },
                },
            },
        }

        response = client.post("/api/memory-providers", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["config"]["auth"]["type"] == "custom"
        assert data["config"]["auth"]["credentials"]["header_value"] == "***ENCRYPTED***"

    def test_create_memory_provider_duplicate_name(self, client):
        """Test that duplicate provider names are rejected"""
        payload = {
            "memory_provider_name": "duplicate-test",
            "config": {
                "url": "http://localhost:8765",
                "auth": {"type": "none"},
            },
        }

        # Create first provider
        response1 = client.post("/api/memory-providers", json=payload)
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to create duplicate
        response2 = client.post("/api/memory-providers", json=payload)
        assert response2.status_code == status.HTTP_409_CONFLICT

    def test_create_memory_provider_token_missing_api_key(self, client):
        """Test validation: token auth requires api_key"""
        payload = {
            "memory_provider_name": "invalid-token-auth",
            "config": {
                "url": "http://localhost:8765",
                "auth": {
                    "type": "token",
                    "credentials": {},  # Missing api_key
                },
            },
        }

        response = client.post("/api/memory-providers", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestMemoryProviderList:
    """Test memory provider listing"""

    def test_list_memory_providers_empty(self, client):
        """Test listing when no providers exist"""
        response = client.get("/api/memory-providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
        assert data["providers"] == []

    def test_list_memory_providers(self, client):
        """Test listing memory providers"""
        # Create multiple providers
        providers = [
            {
                "memory_provider_name": "provider-1",
                "config": {"url": "http://localhost:8765", "auth": {"type": "none"}},
            },
            {
                "memory_provider_name": "provider-2",
                "config": {"url": "http://localhost:8766", "auth": {"type": "none"}},
            },
        ]

        for provider in providers:
            client.post("/api/memory-providers", json=provider)

        # List providers
        response = client.get("/api/memory-providers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 2
        assert len(data["providers"]) == 2


class TestMemoryProviderGet:
    """Test getting individual memory provider"""

    def test_get_memory_provider(self, client):
        """Test getting a specific memory provider"""
        # Create provider
        create_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "test-provider",
                "description": "Test description",
                "config": {"url": "http://localhost:8765", "auth": {"type": "none"}},
            },
        )
        provider_id = create_response.json()["memory_provider_id"]

        # Get provider
        response = client.get(f"/api/memory-providers/{provider_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["memory_provider_id"] == provider_id
        assert data["memory_provider_name"] == "test-provider"
        assert data["description"] == "Test description"

    def test_get_nonexistent_memory_provider(self, client):
        """Test getting a provider that doesn't exist"""
        response = client.get("/api/memory-providers/nonexistent-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestMemoryProviderUpdate:
    """Test memory provider updates"""

    def test_update_memory_provider_config(self, client):
        """Test updating memory provider configuration"""
        # Create provider
        create_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "update-test",
                "config": {"url": "http://localhost:8765", "auth": {"type": "none"}},
            },
        )
        provider_id = create_response.json()["memory_provider_id"]

        # Update provider
        update_payload = {
            "config": {
                "url": "https://new-url.example.com",
                "auth": {
                    "type": "token",
                    "credentials": {"api_key": "new-api-key"},
                },
            }
        }
        response = client.patch(
            f"/api/memory-providers/{provider_id}", json=update_payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["config"]["url"] == "https://new-url.example.com"
        assert data["config"]["auth"]["type"] == "token"

    def test_update_memory_provider_enable_disable(self, client):
        """Test enabling/disabling memory provider"""
        # Create provider
        create_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "disable-test",
                "config": {"url": "http://localhost:8765", "auth": {"type": "none"}},
            },
        )
        provider_id = create_response.json()["memory_provider_id"]

        # Disable provider
        response = client.patch(
            f"/api/memory-providers/{provider_id}", json={"enabled": False}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["enabled"] is False


class TestMemoryProviderDelete:
    """Test memory provider deletion"""

    def test_delete_memory_provider(self, client):
        """Test deleting a memory provider"""
        # Create provider
        create_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "delete-test",
                "config": {"url": "http://localhost:8765", "auth": {"type": "none"}},
            },
        )
        provider_id = create_response.json()["memory_provider_id"]

        # Delete provider
        response = client.delete(f"/api/memory-providers/{provider_id}")

        assert response.status_code == status.HTTP_200_OK

        # Verify it's deleted (soft delete)
        get_response = client.get(f"/api/memory-providers/{provider_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
