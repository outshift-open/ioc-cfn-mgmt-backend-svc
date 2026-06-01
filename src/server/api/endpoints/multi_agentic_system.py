# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter, Depends, HTTPException, status

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognition_engine import CognitionEngineAssociateResponse
from server.schemas.multi_agentic_system import (
    MASQueryByIdentity,
    MasCognitionEngineAssociateRequest,
    MultiAgenticSystem,
    MultiAgenticSystemRequest,
    MultiAgenticSystemResponse,
    MultiAgenticSystems,
    MultiAgenticSystemUpdate,
)
from server.services import multi_agentic_system_service

router = APIRouter()


def check_workspace_exists(workspace_id: str) -> None:
    """Check if workspace exists, raise 404 if not"""
    from server.services.workspace import workspace_service

    if not workspace_service.exists(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )


@router.post(
    "/{workspace_id}/multi-agentic-systems",
    response_model=MultiAgenticSystemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_multi_agentic_system(
    workspace_id: str,
    mas_data: MultiAgenticSystemRequest,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new Multi-Agentic System (MAS) within a workspace

    - **workspace_id**: UUID of the workspace
    - **name**: Unique name within the workspace for the MAS
    - **description**: Optional description of the MAS
    - **agents**: Optional configuration of agents in the system
    - **config**: Optional configuration for managing long-term memories

    Returns the UUID and name of the created MAS
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "create", "multi_agentic_system")
    return multi_agentic_system_service.create(workspace_id, mas_data)


@router.get(
    "/{workspace_id}/multi-agentic-systems",
    response_model=MultiAgenticSystems,
)
def list_multi_agentic_systems(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all Multi-Agentic Systems in a workspace

    - **workspace_id**: UUID of the workspace

    Returns list of MAS in the workspace
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "list", "multi_agentic_system")
    return multi_agentic_system_service.list(workspace_id)


@router.post(
    "/{workspace_id}/multi-agentic-systems/query",
    response_model=MultiAgenticSystems,
)
def query_multi_agentic_systems_by_identity(
    workspace_id: str,
    query: MASQueryByIdentity,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Query Multi-Agentic Systems that have agents with claude identity matching the given identifiers.

    - **workspace_id**: UUID of the workspace
    - **identity_identifiers**: Key-value pairs to match against agent identity_identifiers (e.g. {"xyz": "pqr"})

    Returns list of MAS containing agents with identity_type 'claude' and matching identity_identifiers.
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "list", "multi_agentic_system")
    return multi_agentic_system_service.query_by_identity(workspace_id, query)


@router.get(
    "/{workspace_id}/multi-agentic-systems/{mas_id}",
    response_model=MultiAgenticSystem,
)
def get_multi_agentic_system(
    workspace_id: str,
    mas_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific Multi-Agentic System by ID

    - **workspace_id**: UUID of the workspace
    - **mas_id**: UUID of the multi-agentic system

    Returns detailed MAS information
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "get", "multi_agentic_system")
    return multi_agentic_system_service.get(workspace_id, mas_id)


@router.put(
    "/{workspace_id}/multi-agentic-systems/{mas_id}",
    response_model=MultiAgenticSystem,
)
def update_multi_agentic_system(
    workspace_id: str,
    mas_id: str,
    mas_data: MultiAgenticSystemUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a Multi-Agentic System

    - **workspace_id**: UUID of the workspace
    - **mas_id**: UUID of the multi-agentic system to update
    - **name**: Updated name for the MAS (optional)
    - **description**: Updated description (optional)
    - **agents**: Updated agent configuration (optional)
    - **config**: Updated configuration (optional)

    Returns the updated MAS details
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "update", "multi_agentic_system")
    return multi_agentic_system_service.update(workspace_id, mas_id, mas_data)


@router.delete(
    "/{workspace_id}/multi-agentic-systems/{mas_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_multi_agentic_system(
    workspace_id: str,
    mas_id: str,
    _purge: bool = False,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a Multi-Agentic System

    - **workspace_id**: UUID of the workspace
    - **mas_id**: UUID of the multi-agentic system to delete
    - **_purge**: Optional query parameter. If false (default), performs soft delete. If true, performs hard delete.

    Returns success message
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "delete", "multi_agentic_system")
    multi_agentic_system_service.delete(workspace_id, mas_id, _purge)
    return None


@router.post(
    "/{workspace_id}/multi-agentic-systems/{mas_id}/cognition-engines",
    response_model=CognitionEngineAssociateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Associate CE with MAS",
    description=("Add a Cognition Engine to a Multi-Agentic System. " "The CE's CFN must match the workspace's CFN."),
)
def associate_cognition_engine(
    workspace_id: str,
    mas_id: str,
    request: MasCognitionEngineAssociateRequest,
    auth_user: dict = Depends(get_auth_user),
):
    from server.services.cognition_engine import cognition_engine_service

    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "associate", "multi_agentic_system")
    return cognition_engine_service.associate(mas_id, request.ce_id, auth_user.get("id", "unknown"))


@router.delete(
    "/{workspace_id}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disassociate CE from MAS",
    description="Remove a Cognition Engine from a Multi-Agentic System.",
)
def disassociate_cognition_engine(
    workspace_id: str,
    mas_id: str,
    ce_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    from server.services.cognition_engine import cognition_engine_service

    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "disassociate", "multi_agentic_system")
    cognition_engine_service.disassociate(ce_id, mas_id, auth_user.get("id", "unknown"))
