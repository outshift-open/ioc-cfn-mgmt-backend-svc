from fastapi import APIRouter, Depends, status

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceList,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from server.services.workspace import workspace_service

router = APIRouter()
internal_router = APIRouter()


@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    workspace_data: WorkspaceCreate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new workspace

    - **name**: Name of the workspace (required)
    - **users**: List of user IDs (optional)
    - **config**: Workspace configuration (optional)

    Returns the UUID of the created workspace
    """
    authz_service.require_permission(auth_user, "create", "workspace")
    return workspace_service.create(workspace_data, creator_user_id=auth_user["id"])


@router.get("/", response_model=WorkspaceList)
def list_workspaces(auth_user: dict = Depends(get_auth_user)):
    """
    List workspaces accessible to the user

    Users see only workspaces they are members of. Super admins (future) see all workspaces.
    """
    authz_service.require_permission(auth_user, "get", "workspace")
    return workspace_service.list(user_id=auth_user["id"], user_role=auth_user["role"])


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific workspace by ID

    - **workspace_id**: UUID of the workspace

    Returns detailed workspace information if user has access
    """
    authz_service.require_permission(auth_user, "get", "workspace")
    return workspace_service.get(workspace_id, user_id=auth_user["id"], user_role=auth_user["role"])


@router.put("/{workspace_id}", response_model=WorkspaceDetail)
def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a workspace

    - **workspace_id**: UUID of the workspace
    - **name**: New name for the workspace (optional)

    Returns the updated workspace details if user has access
    """
    authz_service.require_permission(auth_user, "update", "workspace")
    return workspace_service.update(workspace_id, workspace_data, user_id=auth_user["id"], user_role=auth_user["role"])


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: str,
    _purge: bool = False,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a workspace

    - **workspace_id**: UUID of the workspace
    - **_purge**: Optional query parameter. If false (default), performs soft
      delete. If true, performs hard delete.

    Returns success message if user has access
    """
    authz_service.require_permission(auth_user, "delete", "workspace")
    workspace_service.delete(
        workspace_id, _purge, allow_default_delete=False, user_id=auth_user["id"], user_role=auth_user["role"]
    )
    return None


@internal_router.delete("/{workspace_id}", status_code=status.HTTP_200_OK)
def delete_workspace_internal(workspace_id: str, _purge: bool = False):
    """
    Internal delete for workspaces. Allows deleting the Default Workspace,
    still enforces dependency checks.
    """
    return workspace_service.delete(workspace_id, _purge, allow_default_delete=True)
