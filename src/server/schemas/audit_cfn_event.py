# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class AuditCfnEventResponse(BaseModel):
    """Response model for CFN audit events from cfn_cp database."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique audit event ID (UUID)")
    operation_id: Optional[str] = Field(default=None, description="Operation identifier")
    resource_type: str = Field(..., description="Type of the resource (e.g. MAS, WORKSPACE)")
    resource_identifier: str = Field(..., description="Identifier of the resource")
    audit_type: str = Field(..., description="Type of audit event (e.g. RESOURCE_CREATED)")
    audit_resource_identifier: str = Field(..., description="Identifier of the audited resource")
    audit_information: Optional[Dict[str, Any]] = Field(default=None, description="JSONB audit event details")
    audit_extra_information: Optional[str] = Field(default=None, description="Additional information as text")
    created_by: UUID = Field(..., description="UUID of the user who created the event")
    created_on: datetime = Field(..., description="Timestamp when the event was created")
    last_modified_by: UUID = Field(..., description="UUID of the user who last modified the event")
    last_modified_on: datetime = Field(..., description="Timestamp when the event was last modified")


class AuditCfnPageInfo(BaseModel):
    """Pagination metadata matching the upstream cfn-svc response."""

    page: int = Field(..., description="Current 0-based page number")
    pageSize: int = Field(..., description="Requested page size")
    pageCount: int = Field(..., description="Number of elements returned in this page")
    totalElements: int = Field(..., description="Total number of matching records across all pages")


class AuditCfnEventListResponse(BaseModel):
    """Paginated list response matching the upstream cfn-svc shape."""

    data: List[AuditCfnEventResponse] = Field(..., description="List of audit events")
    pageInfo: AuditCfnPageInfo = Field(..., description="Pagination metadata")
