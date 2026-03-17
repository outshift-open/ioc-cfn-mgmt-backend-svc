# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognitive Agent schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CognitiveAgentCreate(BaseModel):
    """Schema for creating a cognitive agent"""

    cognitive_agent_name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    config: Optional[dict] = Field(None, description="Agent-specific configuration")


class CognitiveAgentListItem(BaseModel):
    """Schema for cognitive agent list item"""

    cognitive_agent_id: str
    workspace_id: str
    cognitive_agent_name: str
    description: Optional[str]
    config: Optional[dict]
    enabled: bool
    created_at: datetime


class CognitiveAgentList(BaseModel):
    """Schema for cognitive agent list response"""

    agents: list[CognitiveAgentListItem] = Field(..., description="List of cognitive agents")
    total: int = Field(..., description="Total number of agents")


class CognitiveAgentUpdate(BaseModel):
    """Schema for updating a cognitive agent"""

    cognitive_agent_name: Optional[str] = Field(None, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    config: Optional[dict] = Field(None, description="Agent-specific configuration")
    enabled: Optional[bool] = Field(None, description="Whether agent is enabled")


class CognitiveAgentDetail(BaseModel):
    """Schema for detailed cognitive agent information"""

    cognitive_agent_id: str
    workspace_id: str
    cognitive_agent_name: str
    description: Optional[str]
    config: Optional[dict]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]
