"""Memory Provider schemas — Memory Providers are shared across workspaces"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MemoryProviderConfig(BaseModel):
    """Memory Provider configuration"""

    host: str = Field(..., description="Provider host URL")
    port: int = Field(..., description="Provider port")


class MemoryProviderCreate(BaseModel):
    """Schema for creating a memory provider"""

    memory_provider_id: str = Field(..., description="Memory provider identifier")
    memory_provider_name: str = Field(..., description="Memory provider name")
    provider_type: str = Field(..., description="Provider type (internal, external)")
    provider: str = Field(..., description="Provider name (e.g., ioc-memory-provider)")
    config: Optional[dict] = Field(None, description="Provider-specific configuration")


class MemoryProviderListItem(BaseModel):
    """Schema for memory provider list item"""

    memory_provider_id: str
    memory_provider_name: str
    provider_type: str
    provider: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime


class MemoryProviderList(BaseModel):
    """Schema for memory provider list response"""

    providers: list["MemoryProviderDetail"] = Field(..., description="List of memory providers")
    total: int = Field(..., description="Total number of providers")


class MemoryProviderUpdate(BaseModel):
    """Schema for updating a memory provider"""

    memory_provider_name: Optional[str] = Field(None, description="Memory provider name")
    provider_type: Optional[str] = Field(None, description="Provider type (internal, external)")
    provider: Optional[str] = Field(None, description="Provider name (e.g., ioc-memory-provider)")
    config: Optional[dict] = Field(None, description="Provider-specific configuration")
    enabled: Optional[bool] = Field(None, description="Whether provider is enabled")


class MemoryProviderDetail(BaseModel):
    """Schema for detailed memory provider information"""

    memory_provider_id: str
    memory_provider_name: str
    provider_type: str
    provider: str
    config: Optional[dict]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]
