# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter, HTTPException, Query
from server.services.audit import audit_service
from server.schemas.audit import AuditResponse, AuditListResponse

router = APIRouter()


@router.post("/", status_code=201, response_model=AuditResponse)
def create_audit():
    """
    Create a new audit entry

    Note: Audit entries are created automatically by the system.
    This endpoint is for documentation purposes.
    """
    raise HTTPException(status_code=405, detail="Use system methods to create audit entries")


@router.get("/{audit_id}", status_code=200, response_model=AuditResponse)
def get_audit(audit_id: str):
    """
    Get a specific audit entry by ID
    """
    try:
        audit = audit_service.get_audit(audit_id)
        if not audit:
            raise HTTPException(status_code=404, detail=f"Audit with ID {audit_id} not found")
        return audit
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit: {str(e)}")


@router.get("/", status_code=200, response_model=AuditListResponse)
def list_audits(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    """
    List all audits with pagination
    """
    try:
        audits, total = audit_service.list_audits(skip=skip, limit=limit)
        return {"total": total, "audits": audits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list audits: {str(e)}")


@router.delete("/{audit_id}", status_code=204)
def delete_audit(audit_id: str):
    """
    Delete a specific audit by ID (soft delete)
    """
    try:
        success = audit_service.delete_audit(audit_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Audit with ID {audit_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete audit: {str(e)}")
