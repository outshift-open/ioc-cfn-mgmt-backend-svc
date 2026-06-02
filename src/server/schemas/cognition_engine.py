# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine schemas"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class CognitionEngineRegisterRequest(BaseModel):
    """Schema for CE self-registration (idempotent upsert)"""

    cfn_id: str = Field(..., description="CFN this engine is registering under")
    name: str = Field(..., description="Engine name")
    url: str = Field(..., description="URL for the CFN to reach this engine")
    version: str = Field(..., description="CE software version, e.g. '1.2.3'")
    type: str = Field(
        ..., description="Engine type: 'knowledge_management', 'semantic_negotiation', 'distillation', 'custom'"
    )
    auto_attach: bool = Field(
        False, description="If true, CE is auto-attached to all MAS under the same CFN's workspaces"
    )
    auth: Optional[dict] = Field(None, description='Auth credentials, e.g. {"type": "api_key", "credentials": {...}}')
    capabilities: Optional[List[str]] = Field(default_factory=list, description="Capability names")
    metrics: Optional[List[str]] = Field(default_factory=list, description="Metric names the CE will publish")
    config: Optional[dict] = Field(default_factory=dict, description="CE-level configuration")
    mas_config: Optional[dict] = Field(default_factory=dict, description="MAS-specific config keyed by mas_id")


class CognitionEngineResponse(BaseModel):
    """Schema for CE registration response"""

    ce_id: str
    cfn_id: str
    name: str
    version: str
    type: str
    enabled: bool
    auto_attach: bool
    status: str
    created: bool = Field(..., description="True if new registration, False if existing record was updated")


class CognitionEngineListItem(BaseModel):
    """Schema for a cognition engine in the list response"""

    id: str
    cfn_id: str
    name: str
    version: str
    type: str
    url: str
    enabled: bool
    auto_attach: bool
    status: str
    last_seen: Optional[datetime]
    config: Optional[dict]
    mas_config: Optional[dict]


class CognitionEngineList(BaseModel):
    """Schema for cognition engine list response"""

    cognition_engines: List[CognitionEngineListItem]
    total: int


class CognitionEngineDetail(BaseModel):
    """Schema for detailed cognition engine information"""

    id: str
    cfn_id: str
    name: str
    version: str
    type: str
    url: str
    enabled: bool
    auto_attach: bool
    capabilities: Optional[List[Any]]
    metrics: Optional[List[Any]]
    status: str
    last_seen: Optional[datetime]
    config: Optional[dict]
    mas_config: Optional[dict]
    created_at: datetime
    updated_at: Optional[datetime]


class CognitionEnginePatchRequest(BaseModel):
    """Schema for PATCH /cognition-engines/{id}.

    Only the fields listed here can be updated.
    Attempting to update immutable fields (url, cfn_id, version, name, type)
    will be rejected with 400.
    """

    # Mutable fields — all optional, only provided fields are updated
    enabled: Optional[bool] = Field(None, description="Enable or disable the CE")
    auto_attach: Optional[bool] = Field(None, description="Enable or disable auto-attach to new MAS")
    capabilities: Optional[List[str]] = Field(None, description="Capability names")
    metrics: Optional[List[str]] = Field(None, description="Metric names")
    config: Optional[dict] = Field(None, description="CE-level configuration")
    mas_config: Optional[dict] = Field(None, description="MAS-specific config keyed by mas_id")
    auth: Optional[dict] = Field(None, description="Auth credentials")

    # Immutable fields — declared so callers get a 400 with a clear message rather than silent ignore
    url: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    cfn_id: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    version: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    name: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    type: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")


class CognitionEngineAssociateResponse(BaseModel):
    """Schema for CE-MAS association response"""

    ce_id: str
    mas_id: str
    created_at: datetime


class CognitionEngineHeartbeatResponse(BaseModel):
    """Schema for CE heartbeat response"""

    status: str
    last_seen: datetime
