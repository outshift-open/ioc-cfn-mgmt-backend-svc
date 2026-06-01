# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine API endpoints"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognition_engine import (
    CognitionEngineDetail,
    CognitionEngineHeartbeatResponse,
    CognitionEngineList,
    CognitionEnginePatchRequest,
    CognitionEngineRegisterRequest,
    CognitionEngineResponse,
)
from server.services.cognition_engine import cognition_engine_service

router = APIRouter()


@router.post(
    "/cognition-engines",
    response_model=CognitionEngineResponse,
    summary="Register Cognition Engine",
    description=(
        "Register or update a Cognition Engine with a CFN. "
        "Idempotent: same (cfn_id, name, version) updates the record (200) or creates it (201). "
        "Same name with a different version creates a new record."
    ),
)
def register_cognition_engine(
    engine_data: CognitionEngineRegisterRequest,
    response: Response,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "create", "cognition_engine")
    user_id = auth_user.get("id", "unknown")
    result, created = cognition_engine_service.register(engine_data, user_id)
    response.status_code = 201 if created else 200
    return result


@router.get(
    "/cognition-engines",
    response_model=CognitionEngineList,
    summary="List Cognition Engines",
    description="List cognition engines, optionally filtered by cfn_id and/or status.",
)
def list_cognition_engines(
    cfn_id: Optional[str] = Query(None, description="Filter by CFN ID"),
    status: Optional[str] = Query(None, description="Filter by status: 'online' or 'offline'"),
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "list", "cognition_engine")
    return cognition_engine_service.list(cfn_id=cfn_id, status=status)


@router.get(
    "/cognition-engines/{ce_id}",
    response_model=CognitionEngineDetail,
    summary="Get Cognition Engine",
    description="Get details of a specific cognition engine.",
)
def get_cognition_engine(
    ce_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "get", "cognition_engine")
    return cognition_engine_service.get(ce_id)


@router.patch(
    "/cognition-engines/{ce_id}",
    response_model=CognitionEngineDetail,
    summary="Update Cognition Engine",
    description=(
        "Partially update a Cognition Engine. "
        "Immutable fields (url, cfn_id, version, name, type, auto_attach) cannot be updated — returns 400 if attempted."
    ),
)
def patch_cognition_engine(
    ce_id: str,
    patch_data: CognitionEnginePatchRequest,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "update", "cognition_engine")
    user_id = auth_user.get("id", "unknown")
    return cognition_engine_service.patch(ce_id, patch_data, user_id)


@router.delete(
    "/cognition-engines/{ce_id}",
    status_code=204,
    summary="Deregister Cognition Engine",
    description="Soft-delete (deregister) a cognition engine.",
)
def delete_cognition_engine(
    ce_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "delete", "cognition_engine")
    user_id = auth_user.get("id", "unknown")
    cognition_engine_service.delete(ce_id, user_id)


@router.put(
    "/cognition-engines/{ce_id}/heartbeat",
    response_model=CognitionEngineHeartbeatResponse,
    summary="Cognition Engine Heartbeat",
    description="Update last_seen and flip status to online. Called by the CE to signal it is alive.",
)
def heartbeat_cognition_engine(
    ce_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "heartbeat", "cognition_engine")
    return cognition_engine_service.heartbeat(ce_id)
