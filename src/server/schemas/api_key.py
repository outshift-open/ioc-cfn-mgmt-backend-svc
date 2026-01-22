from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional


class ApiKeyCreate(BaseModel):
    name: str = Field(
        ...,
        description="Human-readable name for the API key",
        min_length=1,
        max_length=200,
    )
    roles: List[str] = Field(
        ...,
        description="List of roles assigned to this API key (e.g., ['admin', 'viewer'])",
        min_length=1,
    )
    workspace_id: Optional[str] = Field(
        None,
        description="Optional workspace ID to associate with this API key",
    )


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "key": "tkf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "key_preview": "tkf_xxx...",
                "name": "Production API Key",
                "roles": ["admin"],
                "workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "created_at": "2024-11-14T10:30:00Z",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the API key")
    key: str = Field(..., description="Full API key (only returned on creation)")
    key_preview: str = Field(..., description="Preview of the API key (first few characters)")
    name: str = Field(..., description="Human-readable name for the API key")
    roles: List[str] = Field(..., description="List of roles assigned to this API key")
    workspace_id: Optional[str] = Field(None, description="Associated workspace ID")
    created_at: datetime = Field(..., description="Timestamp when the API key was created")


class ApiKeyListItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "key_preview": "tkf_abc123...",
                "name": "Production API Key",
                "roles": ["admin"],
                "workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "created_at": "2024-11-14T10:30:00Z",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the API key")
    key_preview: str = Field(..., description="Preview of the API key (first few characters)")
    name: str = Field(..., description="Human-readable name for the API key")
    roles: List[str] = Field(..., description="List of roles assigned to this API key")
    workspace_id: Optional[str] = Field(None, description="Associated workspace ID")
    created_at: datetime = Field(..., description="Timestamp when the API key was created")


class ApiKeyList(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "api_keys": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "key_preview": "tkf_abc123...",
                        "name": "Production API Key",
                        "roles": ["admin"],
                        "workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                        "created_at": "2024-11-14T10:30:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    api_keys: List[ApiKeyListItem]
    total: int
