from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any, List


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
    agents: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration of agents in the system",
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
    agents: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated configuration of agents in the system",
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
                "agents": {"agent1": {"type": "planner"}, "agent2": {"type": "executor"}},
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
    agents: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class MultiAgenticSystems(BaseModel):
    """Schema for listing multi-agentic systems"""

    systems: List[MultiAgenticSystem] = Field(..., description="List of multi-agentic systems in the workspace")
