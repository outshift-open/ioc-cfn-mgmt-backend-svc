# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine schemas"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CECategory(str, Enum):
    """Category of a Cognition Engine.

    - UNKNOWN: Default/unspecified category
    - GAT: Gateway CE (e.g., CASA)
    - COG: Cognition Engines (all other CEs)
    """

    UNKNOWN = "UNKNOWN"
    GAT = "GAT"
    COG = "COG"


class CognitionEngineRegisterRequest(BaseModel):
    """Schema for CE self-registration (idempotent upsert)"""

    cfn_id: str = Field(..., description="CFN this engine is registering under")
    name: str = Field(..., description="Engine name")
    url: str = Field(..., description="URL for the CFN to reach this engine")
    version: str = Field(..., description="CE software version, e.g. '1.2.3'")
    kinds_subkinds: Dict[str, List[str]] = Field(
        ...,
        description=(
            "Map of kind -> list of subkinds, e.g. {'intent': ['mission'], 'exchange': ['team-formation']}. "
            "All supported subkinds must be listed. Required for L9 routing."
        ),
    )
    subprotocols: Optional[List[str]] = Field(
        default=None, description="List of subprotocols supported by this CE, e.g. ['sab']."
    )
    category: CECategory = Field(
        default=CECategory.COG,
        description="CE category: 'UNKNOWN', 'GAT' (Gateway, e.g. CASA), or 'COG' (Cognition, default for most CEs)",
    )
    mas_auto_associate: bool = Field(
        False, description="If true, CE is auto-associated with all MAS under the same CFN's workspaces"
    )
    auth: Optional[dict] = Field(None, description='Auth credentials, e.g. {"type": "api_key", "credentials": {...}}')
    capabilities: Optional[List[str]] = Field(default_factory=list, description="Capability names")
    metrics: Optional[List[str]] = Field(default_factory=list, description="Metric names the CE will publish")
    config: Optional[dict] = Field(default_factory=dict, description="CE-level configuration")
    mas_config: Optional[dict] = Field(
        default_factory=dict,
        description="Factory defaults for per-MAS configuration (e.g. schedule). Copied to each MAS on association and overridable per MAS.",  # noqa: E501
    )


class CognitionEngineResponse(BaseModel):
    """Schema for CE registration response"""

    ce_id: str
    cfn_id: str
    name: str
    version: str
    kinds_subkinds: Optional[Dict[str, List[str]]]
    subprotocols: Optional[List[str]]
    category: CECategory
    enabled: bool
    mas_auto_associate: bool
    status: str
    created: bool = Field(..., description="True if new registration, False if existing record was updated")


class CognitionEngineListItem(BaseModel):
    """Schema for a cognition engine in the list response"""

    id: str
    cfn_id: str
    name: str
    version: str
    kinds_subkinds: Optional[Dict[str, List[str]]]
    subprotocols: Optional[List[str]]
    category: CECategory
    url: str
    enabled: bool
    mas_auto_associate: bool
    status: str
    last_seen: Optional[datetime]
    config: Optional[dict]
    mas_config: Optional[dict]
    created_at: datetime


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
    kinds_subkinds: Optional[Dict[str, List[str]]]
    subprotocols: Optional[List[str]]
    category: CECategory
    url: str
    enabled: bool
    mas_auto_associate: bool
    capabilities: Optional[List[str]]
    metrics: Optional[List[str]]
    status: str
    last_seen: Optional[datetime]
    config: Optional[dict]
    mas_config: Optional[dict]
    created_at: datetime
    updated_at: Optional[datetime]


class CognitionEnginePatchRequest(BaseModel):
    """Schema for PATCH /cognition-engines/{id}.

    Only the fields listed here can be updated.
    Attempting to update immutable fields (cfn_id, version, name, kinds_subkinds, subprotocols, category)
    will be rejected with 400.
    """

    # Mutable fields — all optional, only provided fields are updated
    url: Optional[str] = Field(None, description="URL for the CFN to reach this engine")
    enabled: Optional[bool] = Field(None, description="Enable or disable the CE")
    mas_auto_associate: Optional[bool] = Field(None, description="Enable or disable auto-association to new MAS")
    capabilities: Optional[List[str]] = Field(None, description="Capability names")
    metrics: Optional[List[str]] = Field(None, description="Metric names")
    config: Optional[dict] = Field(None, description="CE-level configuration")
    auth: Optional[dict] = Field(None, description="Auth credentials")

    # Immutable fields — declared so callers get a 400 with a clear message rather than silent ignore
    cfn_id: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    version: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    name: Optional[str] = Field(None, description="Immutable — cannot be updated via PATCH")
    kinds_subkinds: Optional[Dict[str, List[str]]] = Field(None, description="Immutable — cannot be updated via PATCH")
    subprotocols: Optional[List[str]] = Field(None, description="Immutable — cannot be updated via PATCH")
    category: Optional[CECategory] = Field(None, description="Immutable — cannot be updated via PATCH")


class CognitionEngineAssociateResponse(BaseModel):
    """Schema for CE-MAS association response"""

    ce_id: str
    mas_id: str
    created_at: datetime


class CognitionEngineHeartbeatResponse(BaseModel):
    """Schema for CE heartbeat response"""

    status: str
    last_seen: datetime
