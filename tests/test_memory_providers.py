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
                        "access_token": "test_bearer_token_fake",
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


class TestMemoryProviderEncryptionFlow:
    """Test complete encryption/decryption flow for CFN config"""

    def test_encryption_flow_token_auth(self, client, created_workspace):
        """Test memory provider with token auth is encrypted for storage, decrypted for CFN"""
        # 1. Create memory provider with sensitive credentials
        provider_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "encrypted-token-provider",
                "description": "Test provider with token auth",
                "config": {
                    "url": "https://memory.example.com:9003",
                    "shared": True,
                    "auth": {
                        "type": "token",
                        "credentials": {"api_key": "test-fake-api-key-not-real"},
                    },
                },
            },
        )
        
        assert provider_response.status_code == status.HTTP_201_CREATED
        provider_data = provider_response.json()
        provider_id = provider_data["memory_provider_id"]
        
        # 2. Verify API response masks credentials (for API consumers)
        assert provider_data["config"]["auth"]["type"] == "token"
        assert provider_data["config"]["auth"]["credentials"]["api_key"] == "***ENCRYPTED***"
        assert "credentials_encrypted" not in provider_data["config"]["auth"]
        
        # 3. Create MAS using this memory provider
        mas_response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={
                "name": "Encryption Test MAS",
                "description": "MAS for testing encryption flow",
                "shared_memory_provider_id": provider_id,
                "agents": [
                    {
                        "agent_id": "test-agent",
                        "agentic_memory_provider_id": provider_id,
                    }
                ],
            },
        )
        
        assert mas_response.status_code == status.HTTP_201_CREATED
        
        # 4. Register CFN for this workspace  
        cfn_response = client.post(
            "/api/cognitive-fabric-nodes",
            json={"cfn_name": "encryption-test-cfn"},
        )
        
        assert cfn_response.status_code == status.HTTP_201_CREATED
        cfn_id = cfn_response.json()["cfn_id"]
        
        # 5. Associate workspace with CFN
        workspace_update_response = client.put(
            f"/api/workspaces/{created_workspace}",
            json={"cfn_id": cfn_id},
        )
        
        assert workspace_update_response.status_code == status.HTTP_200_OK
        
        # 6. Fetch CFN config (what the actual CFN service receives)
        cfn_config_response = client.get(f"/api/cognitive-fabric-nodes/{cfn_id}")
        
        assert cfn_config_response.status_code == status.HTTP_200_OK
        cfn_config = cfn_config_response.json()
        
        # 7. CRITICAL: Verify credentials are DECRYPTED for CFN consumption
        assert "config" in cfn_config
        assert "memory_providers" in cfn_config["config"]
        
        memory_providers = cfn_config["config"]["memory_providers"]
        assert len(memory_providers) > 0
        
        # Find our provider in the list
        test_provider = None
        for mp in memory_providers:
            if mp["memory_provider_id"] == provider_id:
                test_provider = mp
                break
        
        assert test_provider is not None, "Provider not found in CFN config"
        assert test_provider["config"]["auth"]["type"] == "token"
        
        # The critical assertion: CFN should receive DECRYPTED credentials
        assert "credentials" in test_provider["config"]["auth"]
        assert test_provider["config"]["auth"]["credentials"]["api_key"] == "test-fake-api-key-not-real"
        
        # Should NOT have the encrypted field in CFN config
        assert "credentials_encrypted" not in test_provider["config"]["auth"]

    def test_encryption_flow_bearer_auth(self, client, created_workspace):
        """Test memory provider with bearer auth encryption flow"""
        # Create provider with bearer token
        provider_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "encrypted-bearer-provider",
                "config": {
                    "url": "https://oauth.memory.com",
                    "auth": {
                        "type": "bearer",
                        "credentials": {
                            "access_token": "test_bearer_token_fake",
                            "refresh_token": "test_refresh_token_fake",
                        },
                    },
                },
            },
        )
        
        provider_id = provider_response.json()["memory_provider_id"]
        
        # Verify masked in API response
        credentials = provider_response.json()["config"]["auth"]["credentials"]
        assert credentials["access_token"] == "***ENCRYPTED***"
        # refresh_token may not be returned if not relevant for this auth type
        # Just verify it's either masked or not present
        if "refresh_token" in credentials:
            assert credentials["refresh_token"] == "***ENCRYPTED***"
        
        # Create MAS and CFN association
        mas_response = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={
                "name": "Bearer Auth MAS",
                "shared_memory_provider_id": provider_id,
                "agents": [],
            },
        )
        assert mas_response.status_code == status.HTTP_201_CREATED
        
        cfn_response = client.post(
            "/api/cognitive-fabric-nodes",
            json={"cfn_name": "bearer-test-cfn"},
        )
        cfn_id = cfn_response.json()["cfn_id"]
        
        client.put(
            f"/api/workspaces/{created_workspace}",
            json={"cfn_id": cfn_id},
        )
        
        # Fetch CFN config
        cfn_config = client.get(f"/api/cognitive-fabric-nodes/{cfn_id}").json()
        
        # Verify decrypted for CFN
        memory_providers = cfn_config["config"]["memory_providers"]
        test_provider = next((mp for mp in memory_providers if mp["memory_provider_id"] == provider_id), None)
        
        assert test_provider is not None
        credentials = test_provider["config"]["auth"]["credentials"]
        assert credentials["access_token"] == "test_bearer_token_fake"
        # refresh_token is only included if it was provided
        if "refresh_token" in credentials:
            assert credentials["refresh_token"] == "test_refresh_token_fake"

    def test_encryption_flow_basic_auth(self, client, created_workspace):
        """Test memory provider with basic auth encryption flow"""
        provider_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "encrypted-basic-provider",
                "config": {
                    "url": "https://basic-auth.memory.com",
                    "auth": {
                        "type": "basic",
                        "credentials": {
                            "username": "admin_user",
                            "password": "test_fake_password",
                        },
                    },
                },
            },
        )
        
        provider_id = provider_response.json()["memory_provider_id"]
        
        # Password should be masked
        credentials = provider_response.json()["config"]["auth"]["credentials"]
        assert credentials["password"] == "***ENCRYPTED***"
        # Username is not sensitive, may or may not be masked - just verify it exists
        assert "username" in credentials
        
        # Create MAS and CFN
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={
                "name": "Basic Auth MAS",
                "shared_memory_provider_id": provider_id,
                "agents": [],
            },
        )
        
        cfn_response = client.post(
            "/api/cognitive-fabric-nodes",
            json={"cfn_name": "basic-test-cfn"},
        )
        cfn_id = cfn_response.json()["cfn_id"]
        
        client.put(
            f"/api/workspaces/{created_workspace}",
            json={"cfn_id": cfn_id},
        )
        
        # Fetch CFN config and verify decryption
        cfn_config = client.get(f"/api/cognitive-fabric-nodes/{cfn_id}").json()
        memory_providers = cfn_config["config"]["memory_providers"]
        test_provider = next((mp for mp in memory_providers if mp["memory_provider_id"] == provider_id), None)
        
        assert test_provider is not None
        credentials = test_provider["config"]["auth"]["credentials"]
        assert credentials["username"] == "admin_user"
        assert credentials["password"] == "test_fake_password"

    def test_no_auth_provider_unchanged(self, client, created_workspace):
        """Test that providers with no auth are not affected by encryption logic"""
        provider_response = client.post(
            "/api/memory-providers",
            json={
                "memory_provider_name": "no-auth-provider",
                "config": {
                    "url": "http://localhost:8765",
                    "auth": {"type": "none"},
                },
            },
        )
        
        provider_id = provider_response.json()["memory_provider_id"]
        
        # No credentials to encrypt
        assert provider_response.json()["config"]["auth"]["type"] == "none"
        # credentials should be None or not present for no-auth
        credentials = provider_response.json()["config"]["auth"].get("credentials")
        assert credentials is None or credentials == {}
        
        # Create MAS and CFN
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems",
            json={
                "name": "No Auth MAS",
                "shared_memory_provider_id": provider_id,
                "agents": [],
            },
        )
        
        cfn_response = client.post(
            "/api/cognitive-fabric-nodes",
            json={"cfn_name": "no-auth-cfn"},
        )
        cfn_id = cfn_response.json()["cfn_id"]
        
        client.put(
            f"/api/workspaces/{created_workspace}",
            json={"cfn_id": cfn_id},
        )
        
        # Verify no auth in CFN config either
        cfn_config = client.get(f"/api/cognitive-fabric-nodes/{cfn_id}").json()
        memory_providers = cfn_config["config"]["memory_providers"]
        test_provider = next((mp for mp in memory_providers if mp["memory_provider_id"] == provider_id), None)
        
        assert test_provider is not None
        assert test_provider["config"]["auth"]["type"] == "none"
        # No credentials for no-auth type
        credentials = test_provider["config"]["auth"].get("credentials")
        assert credentials is None or credentials == {}
