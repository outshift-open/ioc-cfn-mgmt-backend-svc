# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine API endpoints"""

from typing import Dict

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognition_engine import (
    CognitionEngineCreate,
    CognitionEngineDetail,
    CognitionEngineList,
    CognitionEngineUpdate,
)
from server.services.cognition_engine import cognition_engine_service

router = APIRouter()


@router.post(
    "/{workspace_id}/cognition-engines",
    response_model=CognitionEngineDetail,
    summary="Create Cognition Engine",
    description="Create a new cognition engine in workspace",
    status_code=201,
)
def create_cognition_engine(
    workspace_id: str,
    engine_data: CognitionEngineCreate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new cognition engine

    Args:
        workspace_id: Workspace identifier
        engine_data: Cognitive engine creation data
        auth_user: Authenticated user

    Returns:
        CognitionEngineDetail with the created engine
    """
    authz_service.require_permission(auth_user, "create", "cognition_engine")
    user_id = auth_user.get("id", "unknown")
    return cognition_engine_service.create(workspace_id, engine_data, user_id)


@router.get(
    "/{workspace_id}/cognition-engines",
    response_model=CognitionEngineList,
    summary="List Cognition Engines",
    description="Get list of all cognition engines in workspace",
)
def list_cognition_engines(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all cognition engines

    Args:
        workspace_id: Workspace identifier
        auth_user: Authenticated user

    Returns:
        CognitionEngineList with all engines
    """
    authz_service.require_permission(auth_user, "list", "cognition_engine")
    return cognition_engine_service.list(workspace_id)


@router.get(
    "/{workspace_id}/cognition-engines/{cognition_engine_id}",
    response_model=CognitionEngineDetail,
    summary="Get Cognition Engine",
    description="Get details of a specific cognition engine",
)
def get_cognition_engine(
    workspace_id: str,
    cognition_engine_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific cognition engine by ID

    Args:
        workspace_id: Workspace identifier
        cognition_engine_id: ID of the cognition engine
        auth_user: Authenticated user

    Returns:
        CognitionEngineDetail with the engine details
    """
    authz_service.require_permission(auth_user, "get", "cognition_engine")
    return cognition_engine_service.get(workspace_id, cognition_engine_id)


@router.patch(
    "/{workspace_id}/cognition-engines/{cognition_engine_id}",
    response_model=CognitionEngineDetail,
    summary="Update Cognition Engine",
    description="Update an existing cognition engine",
)
def update_cognition_engine(
    workspace_id: str,
    cognition_engine_id: str,
    update_data: CognitionEngineUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a cognition engine

    Args:
        workspace_id: Workspace identifier
        cognition_engine_id: ID of the cognition engine to update
        update_data: Cognitive engine update data
        auth_user: Authenticated user

    Returns:
        CognitionEngineDetail with the updated engine
    """
    authz_service.require_permission(auth_user, "update", "cognition_engine")
    user_id = auth_user.get("id", "unknown")
    return cognition_engine_service.update(workspace_id, cognition_engine_id, update_data, user_id)


@router.delete(
    "/{workspace_id}/cognition-engines/{cognition_engine_id}",
    response_model=Dict[str, str],
    summary="Delete Cognition Engine",
    description="Delete a cognition engine (soft delete)",
)
def delete_cognition_engine(
    workspace_id: str,
    cognition_engine_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a cognition engine (soft delete)

    Args:
        workspace_id: Workspace identifier
        cognition_engine_id: ID of the cognition engine to delete
        auth_user: Authenticated user

    Returns:
        Dict with success message
    """
    authz_service.require_permission(auth_user, "delete", "cognition_engine")
    user_id = auth_user.get("id", "unknown")
    return cognition_engine_service.delete(workspace_id, cognition_engine_id, user_id)
