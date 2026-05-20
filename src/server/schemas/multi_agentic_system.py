# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime
from typing import Optional, Dict, Any, List

from server.schemas.memory_provider import MemoryProviderDetail


class AgentIdentity(BaseModel):
    """Schema for agent identity provider configuration"""

    type: str = Field(..., description="Identity provider type (e.g. openclaw, claude_code, or any custom type)")
    identifiers: Dict[str, str] = Field(
        ..., description="Provider-specific identifiers (varies by type)"
    )


class AgentConfig(BaseModel):
    """Schema for individual agent configuration in MAS (input)"""

    agent_id: Optional[str] = Field(None, description="Unique identifier for the agent (server-generated, ignored on input)")
    name: Optional[str] = Field(None, description="Human-readable agent name")
    url: Optional[str] = Field(None, description="Agent endpoint URL")
    identity: Optional[AgentIdentity] = Field(None, description="Identity provider configuration")
    agentic_memory_provider_id: Optional[str] = Field(None, description="Memory provider ID for agent's private memory")
    config: Optional[Dict[str, Any]] = Field(None, description="Agent-specific configuration")


class AgentWithMemory(BaseModel):
    """Schema for agent with full memory provider details (output)"""

    agent_id: str = Field(..., description="Unique identifier for the agent")
    name: Optional[str] = Field(None, description="Human-readable agent name")
    url: Optional[str] = Field(None, description="Agent endpoint URL")
    identity: Optional[AgentIdentity] = Field(None, description="Identity provider configuration")
    agentic_memory: Optional[MemoryProviderDetail] = Field(
        None, description="Full memory provider configuration for agent's private memory"
    )
    config: Optional[Dict[str, Any]] = Field(None, description="Agent-specific configuration")


class MultiAgenticSystemRequest(BaseModel):
    """Schema for creating a new Multi-Agentic System"""

    name: str = Field(
        ...,
        description="Unique name within the workspace for the multi-agentic system",
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = Field(
        None,
        description="Description of the multi-agentic system",
    )
    shared_memory_provider_id: Optional[str] = Field(
        None,
        description="Memory provider ID for shared memory across all agents in MAS",
    )
    agents: Optional[List[AgentConfig]] = Field(
        None,
        description="List of agents in the system with their configurations",
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration object",
    )


class MultiAgenticSystemUpdate(BaseModel):
    """Schema for updating a Multi-Agentic System"""

    name: Optional[str] = Field(
        None,
        description="Updated name for the multi-agentic system",
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = Field(
        None,
        description="Updated description of the multi-agentic system",
    )
    shared_memory_provider_id: Optional[str] = Field(
        None,
        description="Updated memory provider ID for shared memory",
    )
    agents: Optional[List[AgentConfig]] = Field(
        None,
        description="Updated list of agents in the system",
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated configuration object",
    )


class MultiAgenticSystemResponse(BaseModel):
    """Schema for multi-agentic system creation response"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "unique-name-within-a-workspace",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the multi-agentic system")
    name: str = Field(..., description="Name of the multi-agentic system")


class MultiAgenticSystem(BaseModel):
    """Schema for detailed multi-agentic system information"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "workspace_id": "660e8400-e29b-41d4-a716-446655440000",
                "name": "unique-name-within-a-workspace",
                "description": "A system for collaborative AI agents",
                "shared_memory": {
                    "id": "mem-provider-1",
                    "name": "ioc-knowledge-memory-svc",
                    "config": {"host": "ioc-knowledge-memory-svc", "port": 9003},
                },
                "agents": [
                    {
                        "agent_id": "agent-1",
                        "name": "retrieval-agent",
                        "url": "http://localhost:8080",
                        "identity": {
                            "type": "openclaw",
                            "identifiers": {"url": "main::agents::agent-1"},
                        },
                        "agentic_memory": {
                            "id": "mem-provider-2",
                            "name": "ioc-mem0",
                            "config": {"host": "ioc-mem0", "port": 8765},
                        },
                        "config": {"type": "planner"},
                    }
                ],
                "config": {"memory": {"type": "long-term", "retention": "90d"}},
                "created_at": "2024-12-11T10:30:00Z",
                "updated_at": "2024-12-11T10:30:00Z",
            }
        }
    )

    id: str
    workspace_id: str
    name: str
    description: Optional[str] = None
    shared_memory: Optional[MemoryProviderDetail] = Field(
        None, description="Full configuration of shared memory provider for all agents"
    )
    agents: Optional[List[AgentWithMemory]] = Field(
        None, description="List of agents with their memory provider configurations"
    )
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class MultiAgenticSystems(BaseModel):
    """Schema for listing multi-agentic systems"""

    systems: List[MultiAgenticSystem] = Field(..., description="List of multi-agentic systems in the workspace")


class MASQueryByIdentity(BaseModel):
    """Schema for querying MAS by agent identity type and/or identifiers"""

    identity_type: Optional[str] = Field(
        None, description="Identity provider type to filter by (e.g. 'claude', 'openclaw')"
    )
    identity_identifiers: Optional[Dict[str, str]] = Field(
        None, description="Identity identifiers to match against agent identity_identifiers (e.g. {\"xyz\": \"pqr\"})"
    )

    @model_validator(mode="after")
    def at_least_one_filter(self):
        if not self.identity_type and not self.identity_identifiers:
            raise ValueError("At least one of 'identity_type' or 'identity_identifiers' must be provided")
        return self
