from fastapi import APIRouter, status, Depends

from server.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceDetail,
    WorkspaceUpdate,
    WorkspaceList,
)
from server.services.workspace import workspace_service
from server.api.dependencies import get_current_user
from server.authz.authz_service import authz_service

router = APIRouter()
internal_router = APIRouter()


@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new workspace

    - **name**: Name of the workspace (required)
    - **users**: List of user IDs (optional)
    - **config**: Workspace configuration (optional)

    Returns the UUID of the created workspace
    """
    authz_service.require_permission(current_user, "create", "workspace")
    return workspace_service.create_workspace(workspace_data)


@router.get("/", response_model=WorkspaceList)
def list_workspaces(current_user: dict = Depends(get_current_user)):
    """
    List all workspaces

    Returns a list of all workspaces in the system
    """
    authz_service.require_permission(current_user, "get", "workspace")
    return workspace_service.list_workspaces()


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific workspace by ID

    - **workspace_id**: UUID of the workspace

    Returns detailed workspace information
    """
    authz_service.require_permission(current_user, "get", "workspace")
    return workspace_service.get_workspace(workspace_id)


@router.put("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update a workspace

    - **workspace_id**: UUID of the workspace
    - **name**: New name for the workspace (optional)

    Returns the updated workspace details
    """
    authz_service.require_permission(current_user, "update", "workspace")
    return workspace_service.update_workspace(workspace_id, workspace_data)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: str,
    _purge: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a workspace

    - **workspace_id**: UUID of the workspace
    - **_purge**: Optional query parameter. If false (default), performs soft
      delete. If true, performs hard delete.

    Returns success message
    """
    authz_service.require_permission(current_user, "delete", "workspace")
    workspace_service.delete_workspace(workspace_id, _purge, allow_default_delete=False)
    return None


@internal_router.delete("/{workspace_id}", status_code=status.HTTP_200_OK)
def delete_workspace_internal(workspace_id: str, _purge: bool = False):
    """
    Internal delete for workspaces. Allows deleting the Default Workspace,
    still enforces dependency checks.
    """
    return workspace_service.delete_workspace(workspace_id, _purge, allow_default_delete=True)
