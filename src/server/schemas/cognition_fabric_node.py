# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CognitionFabricNodeStatus(str, Enum):
    """Cognition Fabric Node status enumeration"""

    ONLINE = "online"
    OFFLINE = "offline"


class CognitionFabricNodeRegisterRequest(BaseModel):
    """Schema for Cognition Fabric Node registration request"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "cfn-node-prod-1",
                "cfn_config": {"log_level": "info"},
                "ip_address": "192.168.1.100",
                "port": 8080,
            }
        }
    )

    name: str = Field(
        ...,
        description="Human-readable CFN name (unique identifier)",
        min_length=1,
        max_length=255,
    )
    cfn_config: Optional[Dict[str, Any]] = Field(
        None,
        description="CFN configuration used by the node",
    )
    ip_address: Optional[str] = Field(
        None,
        description="IP address of the CFN node",
        max_length=45,
    )
    port: Optional[int] = Field(
        None,
        description="Port number of the CFN node",
        ge=1,
        le=65535,
    )


class CognitionFabricNodeUpdateRequest(BaseModel):
    """Schema for updating Cognition Fabric Node"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "cfn-node-prod-1-updated",
                "cfn_config": {"log_level": "debug"},
                "ip_address": "192.168.1.101",
                "port": 8081,
            }
        }
    )

    name: Optional[str] = Field(
        None,
        description="Updated CFN name",
        min_length=1,
        max_length=255,
    )
    cfn_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated CFN configuration",
    )
    ip_address: Optional[str] = Field(
        None,
        description="Updated IP address of the CFN node",
        max_length=45,
    )
    port: Optional[int] = Field(
        None,
        description="Updated port number of the CFN node",
        ge=1,
        le=65535,
    )


class CognitionFabricNodeResponse(BaseModel):
    """Schema for Cognition Fabric Node response (common response format)"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "cfn-persistent-id-123",
                "workspace_ids": [],
                "name": "cfn-node-prod-1",
                "config": {
                    "workspaces": [],
                    "memory_providers": [],
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

    id: str = Field(..., description="Cognition Fabric Node identifier")
    workspace_ids: List[str] = Field(default_factory=list, description="Associated workspace identifiers")
    name: str = Field(..., description="Cognition Fabric Node name")
    config: Optional[Dict[str, Any]] = Field(None, description="Aggregated configuration including cfn_config")
    status: CognitionFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
    enabled: bool = Field(..., description="Whether node is enabled")
    ip_address: Optional[str] = Field(None, description="IP address of the CFN node")
    port: Optional[int] = Field(None, description="Port number of the CFN node")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")


class CognitionFabricNodeListItem(BaseModel):
    """Schema for Cognition Fabric Node in list view"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "cfn-persistent-id-123",
                "workspace_ids": ["workspace-uuid-1"],
                "name": "cfn-node-prod-1",
                "status": "online",
                "last_seen": "2026-01-30T12:34:56Z",
                "enabled": True,
                "created_at": "2026-01-30T10:00:00Z",
            }
        }
    )

    id: str = Field(..., description="Cognition Fabric Node identifier")
    workspace_ids: List[str] = Field(default_factory=list, description="Associated workspace identifiers")
    name: str = Field(..., description="Cognition Fabric Node name")
    status: CognitionFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
    enabled: bool = Field(..., description="Whether node is enabled")
    created_at: datetime = Field(..., description="Creation timestamp")


class CognitionFabricNodeList(BaseModel):
    """Schema for listing Cognition Fabric Nodes"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nodes": [
                    {
                        "id": "cfn-persistent-id-123",
                        "workspace_ids": ["workspace-uuid-1"],
                        "name": "cfn-node-prod-1",
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

    nodes: List[CognitionFabricNodeListItem] = Field(..., description="List of Cognition Fabric Nodes")
    total: int = Field(..., description="Total number of Cognition Fabric Nodes")


class CognitionFabricNodeHeartbeatResponse(BaseModel):
    """Schema for heartbeat response"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "online",
                "last_seen": "2026-01-30T12:34:56Z",
                "config_timestamp": "2026-01-30T12:34:56Z",
            }
        }
    )

    status: CognitionFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
    config_timestamp: datetime = Field(..., description="Current config timestamp for change detection")


class CognitionFabricNodeSummaryResponse(BaseModel):
    """Schema for Cognition Fabric Node summary response"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "db44357c-e7ef-4db4-a32d-dc12731d87d9",
                "name": "My Cognition Fabric Node",
                "config": {
                    "workspaces": [],
                    "config_timestamp": "2026-03-09T21:10:03.939351Z",
                },
                "status": "online",
                "last_seen": "2026-03-09T22:13:23.994122",
                "enabled": True,
                "ip_address": "172.18.0.8",
                "port": 9002,
                "created_at": "2026-03-09T21:10:03.938397",
                "updated_at": "2026-03-09T22:13:23.993225",
                "created_by": "00000000-0000-0000-0000-000000000000",
                "updated_by": None,
            }
        }
    )

    id: str = Field(..., description="Cognition Fabric Node identifier")
    name: str = Field(..., description="Cognition Fabric Node name")
    config: Dict[str, Any] = Field(..., description="Configuration with workspaces and config_timestamp")
    status: CognitionFabricNodeStatus = Field(..., description="Current node status")
    last_seen: datetime = Field(..., description="Last heartbeat timestamp")
    enabled: bool = Field(..., description="Whether node is enabled")
    ip_address: Optional[str] = Field(None, description="IP address of the CFN node")
    port: Optional[int] = Field(None, description="Port number of the CFN node")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    updated_by: Optional[str] = Field(None, description="Last updater user ID")
