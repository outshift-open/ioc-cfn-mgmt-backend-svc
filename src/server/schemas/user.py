from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "api_key": "ioc_abc123...",
                "api_key_preview": "ioc_abc123...",
            }
        }
    )

    id: str = Field(..., description="Unique identifier for the user")
    api_key: Optional[str] = Field(None, description="Auto-generated API key (only shown once)")
    api_key_preview: Optional[str] = Field(None, description="Preview of the API key")


class User(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "admin",
                "domain": "ioc.local",
                "role": "admin",
                "created_at": "2024-11-14T10:30:00Z",
                "updated_at": "2024-11-14T11:15:00Z",
            }
        }
    )

    id: str
    username: str
    domain: str
    role: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class Users(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "users": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "username": "admin",
                        "domain": "ioc.local",
                        "role": "admin",
                        "created_at": "2024-11-14T10:30:00Z",
                        "updated_at": "2024-11-14T11:15:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    users: List[User]
    total: int
