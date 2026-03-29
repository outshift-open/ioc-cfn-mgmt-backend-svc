# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Policy schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    """Schema for creating a policy"""

    policy_id: str = Field(..., description="Policy identifier")
    policy_name: str = Field(..., description="Policy name")
    config: Optional[dict] = Field(None, description="Policy-specific configuration")


class PolicyListItem(BaseModel):
    """Schema for policy list item"""

    policy_id: str
    workspace_id: str
    policy_name: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime


class PolicyList(BaseModel):
    """Schema for policy list response"""

    policies: list[PolicyListItem] = Field(..., description="List of policies")
    total: int = Field(..., description="Total number of policies")


class PolicyUpdate(BaseModel):
    """Schema for updating a policy"""

    policy_name: Optional[str] = Field(None, description="Policy name")
    config: Optional[dict] = Field(None, description="Policy-specific configuration")
    enabled: Optional[bool] = Field(None, description="Whether policy is enabled")


class PolicyDetail(BaseModel):
    """Schema for detailed policy information"""

    policy_id: str
    workspace_id: str
    policy_name: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]
