# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognitive Engine API endpoints"""

from typing import Dict

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognitive_engine import (
    CognitiveEngineCreate,
    CognitiveEngineDetail,
    CognitiveEngineList,
    CognitiveEngineUpdate,
)
from server.services.cognitive_engine import cognitive_engine_service

router = APIRouter()


@router.post(
    "/{workspace_id}/cognition-engines",
    response_model=CognitiveEngineDetail,
    summary="Create Cognition Engine",
    description="Create a new cognition engine in workspace",
    status_code=201,
)
def create_cognitive_engine(
    workspace_id: str,
    engine_data: CognitiveEngineCreate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new cognitive engine

    Args:
        workspace_id: Workspace identifier
        engine_data: Cognitive engine creation data
        auth_user: Authenticated user

    Returns:
        CognitiveEngineDetail with the created engine
    """
    authz_service.require_permission(auth_user, "create", "cognitive_engine")
    user_id = auth_user.get("id", "unknown")
    return cognitive_engine_service.create(workspace_id, engine_data, user_id)


@router.get(
    "/{workspace_id}/cognition-engines",
    response_model=CognitiveEngineList,
    summary="List Cognition Engines",
    description="Get list of all cognition engines in workspace",
)
def list_cognitive_engines(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all cognitive engines

    Args:
        workspace_id: Workspace identifier
        auth_user: Authenticated user

    Returns:
        CognitiveEngineList with all engines
    """
    authz_service.require_permission(auth_user, "list", "cognitive_engine")
    return cognitive_engine_service.list(workspace_id)


@router.get(
    "/{workspace_id}/cognition-engines/{cognitive_engine_id}",
    response_model=CognitiveEngineDetail,
    summary="Get Cognition Engine",
    description="Get details of a specific cognition engine",
)
def get_cognitive_engine(
    workspace_id: str,
    cognitive_engine_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific cognitive engine by ID

    Args:
        workspace_id: Workspace identifier
        cognitive_engine_id: ID of the cognitive engine
        auth_user: Authenticated user

    Returns:
        CognitiveEngineDetail with the engine details
    """
    authz_service.require_permission(auth_user, "get", "cognitive_engine")
    return cognitive_engine_service.get(workspace_id, cognitive_engine_id)


@router.patch(
    "/{workspace_id}/cognition-engines/{cognitive_engine_id}",
    response_model=CognitiveEngineDetail,
    summary="Update Cognition Engine",
    description="Update an existing cognition engine",
)
def update_cognitive_engine(
    workspace_id: str,
    cognitive_engine_id: str,
    update_data: CognitiveEngineUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a cognitive engine

    Args:
        workspace_id: Workspace identifier
        cognitive_engine_id: ID of the cognitive engine to update
        update_data: Cognitive engine update data
        auth_user: Authenticated user

    Returns:
        CognitiveEngineDetail with the updated engine
    """
    authz_service.require_permission(auth_user, "update", "cognitive_engine")
    user_id = auth_user.get("id", "unknown")
    return cognitive_engine_service.update(workspace_id, cognitive_engine_id, update_data, user_id)


@router.delete(
    "/{workspace_id}/cognition-engines/{cognitive_engine_id}",
    response_model=Dict[str, str],
    summary="Delete Cognition Engine",
    description="Delete a cognition engine (soft delete)",
)
def delete_cognitive_engine(
    workspace_id: str,
    cognitive_engine_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a cognitive engine (soft delete)

    Args:
        workspace_id: Workspace identifier
        cognitive_engine_id: ID of the cognitive engine to delete
        auth_user: Authenticated user

    Returns:
        Dict with success message
    """
    authz_service.require_permission(auth_user, "delete", "cognitive_engine")
    user_id = auth_user.get("id", "unknown")
    return cognitive_engine_service.delete(workspace_id, cognitive_engine_id, user_id)
