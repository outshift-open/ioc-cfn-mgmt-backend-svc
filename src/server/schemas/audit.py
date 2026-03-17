# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AuditResponse(BaseModel):
    """Response model for audit entries"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique audit ID")
    request_id: Optional[str] = Field(default=None, description="Unique request ID")
    resource_type: str = Field(..., description="Type of the resource being audited")
    audit_type: str = Field(..., description="Type of audit action")
    audit_resource_id: Optional[str] = Field(default=None, description="ID of the resource being audited")
    audit_information: Optional[Dict[str, Any]] = Field(
        default=None, description="Information about the audit as a JSON object"
    )
    audit_extra_information: Optional[str] = Field(default=None, description="Additional audit information")
    created_by: Optional[str] = Field(default=None, description="User who created the audit")
    updated_by: Optional[str] = Field(default=None, description="User who last updated the audit")
    deleted_by: Optional[str] = Field(default=None, description="User who deleted the audit")
    created_at: datetime = Field(..., description="Timestamp when the audit was created")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp when the audit was last updated")
    deleted_at: Optional[datetime] = Field(default=None, description="Timestamp when the audit was deleted")


class AuditListResponse(BaseModel):
    """Response model for listing audits"""

    total: int = Field(..., description="Total number of audits")
    audits: list[AuditResponse] = Field(..., description="List of audit entries")
