from fastapi import APIRouter, status, Depends

from server.schemas.multi_agentic_system import (
    MultiAgenticSystemRequest,
    MultiAgenticSystemUpdate,
    MultiAgenticSystemResponse,
    MultiAgenticSystem,
    MultiAgenticSystems,
)
from server.services import mas_service
from server.api.dependencies import get_current_user
from server.authz.authz_service import authz_service

router = APIRouter()


@router.post(
    "/{workspace_id}/multi-agentic-systems",
    response_model=MultiAgenticSystemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_multi_agentic_system(
    workspace_id: str,
    mas_data: MultiAgenticSystemRequest,
    current_user: dict = Depends(get_current_user),
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
    # Note: Using 'workspace' as resource since MAS operations require workspace access
    authz_service.require_permission(current_user, "create", "workspace")
    return mas_service.create_multi_agentic_system(workspace_id, mas_data)


@router.get(
    "/{workspace_id}/multi-agentic-systems",
    response_model=MultiAgenticSystems,
)
def list_multi_agentic_systems(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    List all Multi-Agentic Systems in a workspace

    - **workspace_id**: UUID of the workspace

    Returns list of MAS in the workspace
    """
    authz_service.require_permission(current_user, "get", "workspace")
    return mas_service.list_multi_agentic_systems(workspace_id)


@router.get(
    "/{workspace_id}/multi-agentic-systems/{mas_id}",
    response_model=MultiAgenticSystem,
)
def get_multi_agentic_system(
    workspace_id: str,
    mas_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific Multi-Agentic System by ID

    - **workspace_id**: UUID of the workspace
    - **mas_id**: UUID of the multi-agentic system

    Returns detailed MAS information
    """
    authz_service.require_permission(current_user, "get", "workspace")
    return mas_service.get_multi_agentic_system(workspace_id, mas_id)


@router.put(
    "/{workspace_id}/multi-agentic-systems/{mas_id}",
    response_model=MultiAgenticSystem,
)
def update_multi_agentic_system(
    workspace_id: str,
    mas_id: str,
    mas_data: MultiAgenticSystemUpdate,
    current_user: dict = Depends(get_current_user),
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
    authz_service.require_permission(current_user, "update", "workspace")
    return mas_service.update_multi_agentic_system(workspace_id, mas_id, mas_data)


@router.delete(
    "/{workspace_id}/multi-agentic-systems/{mas_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_multi_agentic_system(
    workspace_id: str,
    mas_id: str,
    _purge: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a Multi-Agentic System

    - **workspace_id**: UUID of the workspace
    - **mas_id**: UUID of the multi-agentic system to delete
    - **_purge**: Optional query parameter. If false (default), performs soft delete. If true, performs hard delete.

    Returns success message
    """
    authz_service.require_permission(current_user, "delete", "workspace")
    mas_service.delete_multi_agentic_system(workspace_id, mas_id, _purge)
    return None
