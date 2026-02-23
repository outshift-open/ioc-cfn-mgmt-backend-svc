from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CognitiveFabricNodeStatus(str, Enum):
    """Cognitive Fabric Node status enumeration"""

    ONLINE = "online"
    OFFLINE = "offline"


class CognitiveFabricNodeRegisterRequest(BaseModel):
    """Schema for Cognitive Fabric Node registration request"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cfn_name": "cfn-node-prod-1",
                "cfn_config": {"log_level": "info"},
            }
        }
    )

    cfn_name: str = Field(
        ...,
        description="Human-readable CFN name (unique identifier)",
        min_length=1,
        max_length=255,
    )
    cfn_config: Optional[Dict[str, Any]] = Field(
        None,
        description="CFN configuration used by the node",
    )


class CognitiveFabricNodeUpdateRequest(BaseModel):
    """Schema for updating Cognitive Fabric Node"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cfn_name": "cfn-node-prod-1-updated",
                "cfn_config": {"log_level": "debug"},
            }
        }
    )

    cfn_name: Optional[str] = Field(
        None,
        description="Updated CFN name",
        min_length=1,
        max_length=255,
    )
    cfn_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated CFN configuration",
    )


class CognitiveFabricNodeResponse(BaseModel):
    """Schema for Cognitive Fabric Node response (common response format)"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cfn_id": "cfn-persistent-id-123",
                "workspace_ids": [],
                "cfn_name": "cfn-node-prod-1",
                "config": {
                    "cfn_config": {"log_level": "info"},
                    "policies": [],
                    "workspaces": [],
                    "cognitive_agents": [],
                    "memory_providers": [],
                    "cognitive_engines": [],
                },
                "status": "offline",
                "last_seen": "2026-02-19T19:46:49.185773",
                "enabled": True,
                "created_at": "2026-02-19T19:46:49.102012",
                "updated_at": "2026-02-19T19:46:49.102012",
                "created_by": "00000000-0000-0000-0000-000000000000",
                "updated_by": None,
            }
        }
    )

    cfn_id: str = Field(..., description="Cognitive Fabric Node identifier")
    workspace_ids: List[str] = Field(default_factory=list, description="Associated workspace identifiers")
    cfn_name: str = Field(..., description="Cognitive Fabric Node name")
    config: Optional[Dict[str, Any]] = Field(None, description="Aggregated configuration including cfn_config")
    status: CognitiveFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
    enabled: bool = Field(..., description="Whether node is enabled")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")


class CognitiveFabricNodeListItem(BaseModel):
    """Schema for Cognitive Fabric Node in list view"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cfn_id": "cfn-persistent-id-123",
                "workspace_ids": ["workspace-uuid-1"],
                "cfn_name": "cfn-node-prod-1",
                "status": "online",
                "last_seen": "2026-01-30T12:34:56Z",
                "enabled": True,
                "created_at": "2026-01-30T10:00:00Z",
            }
        }
    )

    cfn_id: str = Field(..., description="Cognitive Fabric Node identifier")
    workspace_ids: List[str] = Field(default_factory=list, description="Associated workspace identifiers")
    cfn_name: str = Field(..., description="Cognitive Fabric Node name")
    status: CognitiveFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
    enabled: bool = Field(..., description="Whether node is enabled")
    created_at: datetime = Field(..., description="Creation timestamp")


class CognitiveFabricNodeList(BaseModel):
    """Schema for listing Cognitive Fabric Nodes"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": [
                    {
                        "cfn_id": "cfn-persistent-id-123",
                        "workspace_ids": ["workspace-uuid-1"],
                        "cfn_name": "cfn-node-prod-1",
                        "status": "online",
                        "last_seen": "2026-01-30T12:34:56Z",
                        "enabled": True,
                        "created_at": "2026-01-30T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    nodes: List[CognitiveFabricNodeListItem] = Field(..., description="List of Cognitive Fabric Nodes")
    total: int = Field(..., description="Total number of Cognitive Fabric Nodes")


class CognitiveFabricNodeHeartbeatResponse(BaseModel):
    """Schema for heartbeat response"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "online",
                "last_seen": "2026-01-30T12:34:56Z",
            }
        }
    )

    status: CognitiveFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
