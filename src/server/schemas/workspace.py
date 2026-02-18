from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional, Dict, Any

from server.schemas.workspace_member import WorkspaceMemberDetail


class WorkspaceCreate(BaseModel):
    name: str = Field(
        ...,
        description="Name of the workspace",
        min_length=1,
        max_length=100,
    )
    cfn_id: str = Field(
        ...,
        description="CFN identifier to associate with this workspace (required)",
        min_length=1,
        max_length=255,
    )
    config: Dict[str, Any] = Field(default_factory=dict, description="Workspace configuration settings")


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"id": "550e8400-e29b-41d4-a716-446655440000"}})

    id: str = Field(..., description="Unique identifier for the workspace")


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Updated name of the workspace",
        min_length=1,
        max_length=100,
    )
    cfn_id: Optional[str] = Field(
        None,
        description="CFN identifier to reassign workspace to a different CFN",
        min_length=1,
        max_length=255,
    )


class WorkspaceDetail(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "My Workspace",
                "cfn_id": "cfn-node-001",
                "created_at": "2024-11-14T10:30:00Z",
                "updated_at": "2024-11-14T11:15:00Z",
                "created_by": "user-123",
                "updated_by": "user-456",
                "members": [],
                "config": {},
            }
        }
    )

    id: str
    name: str
    cfn_id: Optional[str] = Field(None, description="CFN identifier that manages this workspace")
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_by_username: Optional[str] = Field(None, description="Username of the workspace creator")
    updated_by: Optional[str] = None
    members: List[WorkspaceMemberDetail] = Field(default_factory=list, description="List of workspace members")
    config: Optional[Dict[str, Any]] = None


class WorkspaceList(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workspaces": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "My Workspace",
                        "created_at": "2024-11-14T10:30:00Z",
                        "updated_at": "2024-11-14T11:15:00Z",
                        "created_by": "user-123",
                        "updated_by": "user-456",
                        "members": [],
                        "config": {},
                    }
                ],
                "total": 1,
            }
        }
    )

    workspaces: List[WorkspaceDetail]
    total: int
