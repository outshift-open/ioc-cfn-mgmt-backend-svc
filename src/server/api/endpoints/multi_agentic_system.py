from fastapi import APIRouter, Depends, HTTPException, status

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.multi_agentic_system import (
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
