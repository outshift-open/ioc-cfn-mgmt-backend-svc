# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CFN Audit Event API endpoints.

Read-only endpoints for querying audit events from ioc-cfn-svc
via its internal HTTP API.
"""

from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from server.schemas.audit_cfn_event import AuditCfnEventListResponse, AuditCfnEventResponse
from server.services.audit_cfn_event import CfnUpstreamError, audit_cfn_event_service

router = APIRouter()


@router.get(
    "/",
    status_code=200,
    response_model=AuditCfnEventListResponse,
    summary="List CFN Audit Events",
    description=(
        "Retrieve a paginated list of audit events from ioc-cfn-svc. "
        "Supports optional filtering by `resource_type` and `audit_type`."
    ),
    responses={
        200: {"description": "Paginated list of audit events returned successfully"},
        500: {"description": "Internal server error while querying ioc-cfn-svc"},
    },
)
def list_audit_events(
    page: int = Query(0, ge=0, description="0-based page number"),
    pageSize: int = Query(
        default=None,
        ge=1,
        description=(
            "Number of records per page. "
            "Defaults to DEFAULT_PAGE_SIZE env var (fallback 20). "
            "Clamped to MAX_PAGE_SIZE env var (fallback 100)."
        ),
    ),
    resource_type: Optional[str] = Query(
        None,
        description=(
            "Filter by resource type "
            "(e.g. MAS, MAS-AGENT, COGNITION_ENGINE, POLICY_ENFORCER, MEMORY_PROVIDER, WORKFLOW, TASK)"
        ),
    ),
    audit_type: Optional[str] = Query(
        None,
        description=(
            "Filter by audit type (e.g. RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED, "
            "RESOURCE_PURGED, RESOURCE_PRUNED, KNOWLEDGE_INGESTION, KNOWLEDGE_QUERY, "
            "MEMORY_OPERATION, SHARED_MEMORY_OPERATION, AGENT_MEMORY_OPERATION)"
        ),
    ),
):
    """
    List all CFN audit events with optional filtering and pagination.

    - **page**: 0-based page number (default 0)
    - **pageSize**: Number of records per page (default 20, max 100)
    - **resource_type**: Optional filter — e.g. `MAS`, `MAS-AGENT`, `COGNITION_ENGINE`
    - **audit_type**: Optional filter — e.g. `RESOURCE_CREATED`, `SHARED_MEMORY_OPERATION`
    """
    try:
        result = audit_cfn_event_service.list_audit_events(
            page=page, page_size=pageSize, resource_type=resource_type, audit_type=audit_type
        )
        return JSONResponse(content=result)
    except CfnUpstreamError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"failed to list audit events: {str(e)}"}
        )


@router.get(
    "/{eventId}",
    status_code=200,
    response_model=AuditCfnEventResponse,
    summary="Get CFN Audit Event by ID",
    description="Retrieve a single audit event from ioc-cfn-svc by its UUID.",
    responses={
        200: {"description": "Audit event returned successfully"},
        400: {"description": "Invalid event ID"},
        404: {"description": "Audit event not found"},
        500: {"description": "Internal server error while querying ioc-cfn-svc"},
    },
)
def get_audit_event(eventId: str):
    """
    Get a specific CFN audit event by UUID.

    - **eventId**: The UUID of the audit event to retrieve
    """
    try:
        audit_event = audit_cfn_event_service.get_audit_event(eventId)
        if not audit_event:
            return JSONResponse(
                status_code=404, content={"error": "audit event not found"}
            )
        return JSONResponse(content=audit_event)
    except CfnUpstreamError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"failed to retrieve audit event: {str(e)}"},
        )
