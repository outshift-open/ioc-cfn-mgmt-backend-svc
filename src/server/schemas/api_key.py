from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(
        ...,
        description="Human-readable name for the API key",
        min_length=1,
        max_length=200,
    )


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "key": "ioc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "key_preview": "ioc_xxx...",
                "name": "Production API Key",
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "created_at": "2024-11-14T10:30:00Z",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the API key")
    key: str = Field(..., description="Full API key (only returned on creation)")
    key_preview: str = Field(..., description="Preview of the API key (first few characters)")
    name: str = Field(..., description="Human-readable name for the API key")
    user_id: str = Field(..., description="ID of the user who owns this API key")
    created_at: datetime = Field(..., description="Timestamp when the API key was created")


class ApiKeyListItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "key_preview": "ioc_abc123...",
                "name": "Production API Key",
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "created_at": "2024-11-14T10:30:00Z",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the API key")
    key_preview: str = Field(..., description="Preview of the API key (first few characters)")
    name: str = Field(..., description="Human-readable name for the API key")
    user_id: str = Field(..., description="ID of the user who owns this API key")
    created_at: datetime = Field(..., description="Timestamp when the API key was created")


class ApiKeyList(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "api_keys": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "key_preview": "ioc_abc123...",
                        "name": "Production API Key",
                        "user_id": "550e8400-e29b-41d4-a716-446655440002",
                        "created_at": "2024-11-14T10:30:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    api_keys: List[ApiKeyListItem]
    total: int
