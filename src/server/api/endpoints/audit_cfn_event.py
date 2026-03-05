"""CFN Audit Event API endpoints.

Read-only endpoints for querying audit events from the cfn_cp database,
which is populated by the ioc-cfn-svc (Cognitive Fabric Node service).
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from server.schemas.audit_cfn_event import AuditCfnEventResponse, AuditCfnEventListResponse
from server.services.audit_cfn_event import audit_cfn_event_service

router = APIRouter()


@router.get(
    "/",
    status_code=200,
    response_model=AuditCfnEventListResponse,
    summary="List CFN Audit Events",
    description=(
        "Retrieve a paginated list of audit events from the CFN control-plane database (cfn_cp). "
        "Supports optional filtering by `resource_type` and `audit_type`."
    ),
    responses={
        200: {"description": "List of audit events returned successfully"},
        500: {"description": "Internal server error while querying cfn_cp database"},
    },
)
def list_audit_events(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    resource_type: Optional[str] = Query(
        None,
        description="Filter by resource type (e.g. MAS, WORKSPACE, COGNITIVE_FABRIC_NODE)",
    ),
    audit_type: Optional[str] = Query(
        None,
        description="Filter by audit type (e.g. RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED)",
    ),
):
    """
    List all CFN audit events with optional filtering and pagination.

    - **skip**: Offset for pagination (default 0)
    - **limit**: Max results per page (default 100, max 1000)
    - **resource_type**: Optional filter — e.g. `MAS`, `WORKSPACE`, `COGNITIVE_FABRIC_NODE`
    - **audit_type**: Optional filter — e.g. `RESOURCE_CREATED`, `RESOURCE_UPDATED`, `RESOURCE_DELETED`
    """
    try:
        audit_events, total = audit_cfn_event_service.list_audit_events(
            skip=skip, limit=limit, resource_type=resource_type, audit_type=audit_type
        )
        return {"total": total, "audit_events": audit_events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list audit events: {str(e)}")


@router.get(
    "/{audit_event_id}",
    status_code=200,
    response_model=AuditCfnEventResponse,
    summary="Get CFN Audit Event by ID",
    description="Retrieve a single audit event from the CFN control-plane database by its UUID.",
    responses={
        200: {"description": "Audit event returned successfully"},
        404: {"description": "Audit event not found"},
        500: {"description": "Internal server error while querying cfn_cp database"},
    },
)
def get_audit_event(audit_event_id: str):
    """
    Get a specific CFN audit event by UUID.

    - **audit_event_id**: The UUID of the audit event to retrieve
    """
    try:
        audit_event = audit_cfn_event_service.get_audit_event(audit_event_id)
        if not audit_event:
            raise HTTPException(status_code=404, detail=f"Audit event with ID {audit_event_id} not found")
        return audit_event
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit event: {str(e)}")
