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
from server.services.workspace_member import workspace_member_service

router = APIRouter()


def require_workspace_read_access(workspace_id: str, auth_user: dict) -> None:
    """Check if user has read access to workspace (admin or viewer)"""
    from server.services.workspace import workspace_service

    # Check if workspace exists first
    if not workspace_service.exists(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    user_role = auth_user.get("role")

    # Super admins have access to all workspaces
    if user_role == "super_admin":
        return

    # Check workspace membership - must be admin or viewer
    member_role = workspace_member_service.get_member_role(workspace_id, auth_user["id"])
    if member_role not in ["admin", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You must be a workspace admin or viewer",
        )


def require_workspace_write_access(workspace_id: str, auth_user: dict) -> None:
    """Check if user has write access to workspace (admin only)"""
    from server.services.workspace import workspace_service

    # Check if workspace exists first
    if not workspace_service.exists(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    user_role = auth_user.get("role")

    # Super admins have access to all workspaces
    if user_role == "super_admin":
        return

    # Check workspace membership - must be admin
    member_role = workspace_member_service.get_member_role(workspace_id, auth_user["id"])
    if member_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You must be a workspace admin",
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
    require_workspace_write_access(workspace_id, auth_user)
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
    require_workspace_read_access(workspace_id, auth_user)
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
    require_workspace_read_access(workspace_id, auth_user)
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
    require_workspace_write_access(workspace_id, auth_user)
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
    require_workspace_write_access(workspace_id, auth_user)
    multi_agentic_system_service.delete(workspace_id, mas_id, _purge)
    return None
