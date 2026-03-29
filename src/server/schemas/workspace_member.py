# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum


class WorkspaceRole(str, Enum):
    """Workspace-level roles"""

    ADMIN = "admin"
    VIEWER = "viewer"
    GUEST = "guest"


class WorkspaceMemberCreate(BaseModel):
    """Schema for creating a new workspace member"""

    user_id: str = Field(..., description="User ID to add as member")
    role: WorkspaceRole = Field(..., description="Role to assign (admin/viewer/guest)")


class WorkspaceMemberDetail(BaseModel):
    """Schema for workspace member details"""

    id: str
    workspace_id: str
    user_id: str
    username: Optional[str] = Field(None, description="Username joined from user table")
    role: WorkspaceRole
    joined_at: datetime
    is_creator: bool = Field(False, description="True if this member created the workspace")


class WorkspaceMemberList(BaseModel):
    """Schema for list of workspace members"""

    members: List[WorkspaceMemberDetail]
    total: int


class WorkspaceMemberRoleUpdate(BaseModel):
    """Schema for updating a member's role"""

    role: WorkspaceRole = Field(..., description="New role to assign")
