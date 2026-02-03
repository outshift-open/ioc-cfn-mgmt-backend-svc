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
                "cfn_id": "cfn-persistent-id-123",
                "cfn_name": "cfn-node-prod-1",
                "cfn_config": {"max_connections": 100, "memory_limit": "4GB"},
            }
        }
    )

    cfn_id: str = Field(
        ...,
        description="Persistent CFN identifier (provided by CFN, immutable)",
        min_length=1,
        max_length=255,
    )
    cfn_name: str = Field(
        ...,
        description="Human-readable CFN name (can be updated)",
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
                "cfn_config": {"max_connections": 200, "memory_limit": "8GB"},
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


class CognitiveFabricNodeRegisterResponse(BaseModel):
    """Schema for Cognitive Fabric Node registration response"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cfn_id": "cfn-persistent-id-123",
                "cfn_name": "cfn-node-prod-1",
                "status": "offline",
                "cloud_config": {
                    "max_connections": 200,
                    "memory_limit": "8GB",
                    "workspace_id": "workspace-uuid",
                    "log_level": "INFO",
                    "features": ["reasoning", "memory"],
                },
            }
        }
    )

    cfn_id: str = Field(..., description="Cognitive Fabric Node identifier")
    cfn_name: str = Field(..., description="Cognitive Fabric Node name")
    status: CognitiveFabricNodeStatus = Field(..., description="Current node status")
    cloud_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Cloud configuration for node to apply",
    )


class CognitiveFabricNodeDetail(BaseModel):
    """Schema for detailed Cognitive Fabric Node information"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cfn_id": "cfn-persistent-id-123",
                "workspace_id": "workspace-uuid",
                "cfn_name": "cfn-node-prod-1",
                "cfn_config": {"max_connections": 100, "memory_limit": "4GB"},
                "cloud_config": {
                    "workspace_id": "workspace-uuid",
                    "log_level": "INFO",
                    "features": ["reasoning", "memory"],
                },
                "status": "online",
                "last_seen": "2026-01-30T12:34:56Z",
                "enabled": True,
                "created_at": "2026-01-30T10:00:00Z",
                "updated_at": "2026-01-30T12:00:00Z",
                "created_by": "user-id",
                "updated_by": "user-id",
            }
        }
    )

    cfn_id: str = Field(..., description="Cognitive Fabric Node identifier")
    workspace_id: str = Field(..., description="Workspace identifier")
    cfn_name: str = Field(..., description="Cognitive Fabric Node name")
    cfn_config: Optional[Dict[str, Any]] = Field(None, description="Node configuration")
    cloud_config: Optional[Dict[str, Any]] = Field(None, description="Cloud configuration")
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
                "workspace_id": "workspace-uuid",
                "cfn_name": "cfn-node-prod-1",
                "status": "online",
                "last_seen": "2026-01-30T12:34:56Z",
                "enabled": True,
                "created_at": "2026-01-30T10:00:00Z",
            }
        }
    )

    cfn_id: str = Field(..., description="Cognitive Fabric Node identifier")
    workspace_id: str = Field(..., description="Workspace identifier")
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
                        "workspace_id": "workspace-uuid",
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
