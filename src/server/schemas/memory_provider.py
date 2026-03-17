# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Memory Provider schemas — Memory Providers are shared across workspaces"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class MemoryProviderAuthCredentials(BaseModel):
    """Auth credentials - structure varies by auth type"""

    api_key: Optional[str] = Field(None, description="API key for token-based auth")

    access_token: Optional[str] = Field(None, description="Access token for bearer auth")

    username: Optional[str] = Field(None, description="Username for basic auth")
    password: Optional[str] = Field(None, description="Password for basic auth")

    header_name: Optional[str] = Field(None, description="Custom header name")
    header_value: Optional[str] = Field(None, description="Custom header value")


class MemoryProviderAuthConfig(BaseModel):
    """Authentication configuration for memory provider"""

    type: Literal["none", "token", "bearer", "basic", "custom"] = Field(
        "none", description="Auth type: none, token, bearer, basic, custom"
    )
    credentials: Optional[MemoryProviderAuthCredentials] = Field(
        None, description="Auth credentials (will be encrypted in database)"
    )

    @model_validator(mode="after")
    def validate_credentials(self):
        """Validate that required credentials are provided for each auth type"""
        if self.type == "none":
            return self

        if not self.credentials:
            raise ValueError(f"Credentials required for auth type '{self.type}'")

        if self.type == "token":
            if not self.credentials.api_key:
                raise ValueError("'api_key' required for token auth")

        elif self.type == "bearer":
            if not self.credentials.access_token:
                raise ValueError("'access_token' required for bearer auth")

        elif self.type == "basic":
            if not self.credentials.username or not self.credentials.password:
                raise ValueError("'username' and 'password' required for basic auth")

        elif self.type == "custom":
            if not self.credentials.header_name or not self.credentials.header_value:
                raise ValueError("'header_name' and 'header_value' required for custom auth")

        return self


class MemoryProviderConfig(BaseModel):
    """Memory Provider configuration"""

    url: str = Field(..., description="Provider URL (e.g., http://localhost:8765)")
    auth: MemoryProviderAuthConfig = Field(
        default_factory=MemoryProviderAuthConfig, description="Authentication configuration"
    )
    shared: Optional[bool] = Field(False, description="Whether provider is shared")


class MemoryProviderCreate(BaseModel):
    """Schema for creating a memory provider"""

    memory_provider_name: str = Field(..., description="Memory provider name")
    description: Optional[str] = Field(None, description="Description of the memory provider")
    config: MemoryProviderConfig = Field(..., description="Provider configuration")


class MemoryProviderUpdate(BaseModel):
    """Schema for updating a memory provider"""

    memory_provider_name: Optional[str] = Field(None, description="Memory provider name")
    description: Optional[str] = Field(None, description="Description of the memory provider")
    config: Optional[MemoryProviderConfig] = Field(None, description="Provider configuration")
    enabled: Optional[bool] = Field(None, description="Whether provider is enabled")


class MemoryProviderDetail(BaseModel):
    """Schema for detailed memory provider information"""

    memory_provider_id: str
    memory_provider_name: str
    description: Optional[str]
    config: Optional[dict]  # Use dict for response to allow flexible structure
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]


class MemoryProviderListItem(BaseModel):
    """Schema for memory provider list item"""

    memory_provider_id: str
    memory_provider_name: str
    description: Optional[str]
    config: Optional[dict]
    enabled: bool
    created_at: datetime


class MemoryProviderList(BaseModel):
    """Schema for memory provider list response"""

    providers: list[MemoryProviderDetail] = Field(..., description="List of memory providers")
    total: int = Field(..., description="Total number of providers")
