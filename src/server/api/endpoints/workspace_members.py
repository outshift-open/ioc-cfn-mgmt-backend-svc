from fastapi import APIRouter, Depends, HTTPException, status

from server.auth.auth import get_auth_user
from server.schemas.workspace_member import (
    WorkspaceMemberDetail,
    WorkspaceMemberList,
    WorkspaceMemberRoleUpdate,
)
from server.services.workspace_member import workspace_member_service

router = APIRouter()


def require_workspace_admin(workspace_id: str, auth_user: dict) -> None:
    """Check if user is an admin of the workspace"""
    # Global admin has access to all workspaces
    if auth_user["role"] == "admin":
        return

    # Check workspace membership and role
    member_role = workspace_member_service.get_member_role(workspace_id, auth_user["id"])
    if member_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace admins can perform this action",
        )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberList,
)
def list_members(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all members of a workspace

    - **workspace_id**: UUID of the workspace

    Returns a list of all workspace members with their roles
    """
    # Any member can view other members (consider tightening this if needed)
    if auth_user["role"] != "admin":
        if not workspace_member_service.is_member(workspace_id, auth_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be a member of this workspace",
            )

    return workspace_member_service.list_members(workspace_id)


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    workspace_id: str,
    user_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Remove a member from a workspace (admin only, cannot remove self)

    - **workspace_id**: UUID of the workspace
    - **user_id**: UUID of the user to remove

    Returns success message
    """
    require_workspace_admin(workspace_id, auth_user)

    # Prevent admin from removing themselves
    if user_id == auth_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot remove yourself from the workspace",
        )

    workspace_member_service.remove_member(workspace_id, user_id, removed_by=auth_user["id"])
    return None


@router.put(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberDetail,
)
def update_member_role(
    workspace_id: str,
    user_id: str,
    role_update: WorkspaceMemberRoleUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a member's role in a workspace (admin only)

    - **workspace_id**: UUID of the workspace
    - **user_id**: UUID of the user
    - **role**: New role to assign (admin/viewer/guest)

    Returns the updated member details
    """
    require_workspace_admin(workspace_id, auth_user)

    return workspace_member_service.update_member_role(
        workspace_id, user_id, role_update.role.value, updated_by=auth_user["id"]
    )
