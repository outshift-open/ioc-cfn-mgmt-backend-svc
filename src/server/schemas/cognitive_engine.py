"""Cognitive Engine schemas"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CognitiveEngineCreate(BaseModel):
    """Schema for creating a cognitive engine"""

    cognitive_engine_id: str = Field(..., description="Engine identifier")
    cognitive_engine_name: str = Field(..., description="Engine name")
    config: Optional[dict] = Field(None, description="Engine-specific configuration")


class CognitiveEngineListItem(BaseModel):
    """Schema for cognitive engine list item"""

    cognitive_engine_id: str
    workspace_id: str
    cognitive_engine_name: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime


class CognitiveEngineList(BaseModel):
    """Schema for cognitive engine list response"""

    engines: list[CognitiveEngineListItem] = Field(..., description="List of cognitive engines")
    total: int = Field(..., description="Total number of engines")


class CognitiveEngineUpdate(BaseModel):
    """Schema for updating a cognitive engine"""

    cognitive_engine_name: Optional[str] = Field(None, description="Engine name")
    config: Optional[dict] = Field(None, description="Engine-specific configuration")
    enabled: Optional[bool] = Field(None, description="Whether engine is enabled")


class CognitiveEngineDetail(BaseModel):
    """Schema for detailed cognitive engine information"""

    cognitive_engine_id: str
    workspace_id: str
    cognitive_engine_name: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]
