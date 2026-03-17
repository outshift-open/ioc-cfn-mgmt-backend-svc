# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional
from enum import Enum


class InvitationStatus(str, Enum):
    """Invitation status values"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class WorkspaceInvitationCreate(BaseModel):
    """Schema for creating a workspace invitation"""

    invitee_username: str = Field(..., description="Username of user to invite")
    role: str = Field(..., description="Role to assign (admin/viewer/guest)")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ["admin", "viewer", "guest"]
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v


class WorkspaceInvitationDetail(BaseModel):
    """Schema for workspace invitation details"""

    id: str
    workspace_id: str
    workspace_name: Optional[str] = Field(None, description="Workspace name joined from workspace table")
    inviter_id: str
    inviter_username: Optional[str] = Field(None, description="Inviter username joined from user table")
    invitee_username: str
    role: str
    status: InvitationStatus
    created_at: datetime
    expires_at: datetime
    responded_at: Optional[datetime] = None


class WorkspaceInvitationList(BaseModel):
    """Schema for list of workspace invitations"""

    invitations: List[WorkspaceInvitationDetail]
    total: int


class WorkspaceInvitationResponse(BaseModel):
    """Schema for invitation creation response"""

    id: str


class WorkspaceInvitationAcceptResponse(BaseModel):
    """Schema for invitation acceptance response"""

    message: str
    workspace_id: str
    workspace_name: str
    assigned_role: str
