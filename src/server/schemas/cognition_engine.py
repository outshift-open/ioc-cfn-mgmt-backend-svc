# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CognitionEngineCreate(BaseModel):
    """Schema for creating a cognition engine"""

    name: str = Field(..., description="Engine name")
    config: Optional[dict] = Field(None, description="Engine-specific configuration")


class CognitionEngineListItem(BaseModel):
    """Schema for cognition engine list item"""

    id: str
    workspace_id: str
    name: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime


class CognitionEngineList(BaseModel):
    """Schema for cognition engine list response"""

    engines: list[CognitionEngineListItem] = Field(..., description="List of cognition engines")
    total: int = Field(..., description="Total number of engines")


class CognitionEngineUpdate(BaseModel):
    """Schema for updating a cognition engine"""

    name: Optional[str] = Field(None, description="Engine name")
    config: Optional[dict] = Field(None, description="Engine-specific configuration")
    enabled: Optional[bool] = Field(None, description="Whether engine is enabled")


class CognitionEngineDetail(BaseModel):
    """Schema for detailed cognition engine information"""

    id: str
    workspace_id: str
    name: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]
