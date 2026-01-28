from fastapi import APIRouter, status, Depends, HTTPException

from server.schemas.workspace_invitation import (
    WorkspaceInvitationCreate,
    WorkspaceInvitationResponse,
    WorkspaceInvitationList,
    InvitationAcceptRequest,
    InvitationDeclineRequest,
)
from server.services.workspace_invitation import workspace_invitation_service
from server.services.workspace_member import workspace_member_service
from server.api.dependencies import get_current_user

router = APIRouter()


def require_workspace_admin(workspace_id: str, current_user: dict) -> None:
    """Check if user is an admin of the workspace"""
    # Global admin has access to all workspaces
    if current_user["role"] == "admin":
        return

    # Check workspace membership and role
    member_role = workspace_member_service.get_member_role(workspace_id, current_user["id"])
    if member_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace admins can perform this action",
        )


@router.post(
    "/workspaces/{workspace_id}/invitations",
    response_model=WorkspaceInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    workspace_id: str,
    invitation_data: WorkspaceInvitationCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a workspace invitation (admin only)

    - **workspace_id**: UUID of the workspace
    - **invitee_username**: Username of user to invite
    - **role**: Role to assign (admin/viewer/guest)

    Returns the UUID of the created invitation
    """
    require_workspace_admin(workspace_id, current_user)

    return workspace_invitation_service.create_invitation(
        workspace_id=workspace_id,
        inviter_id=current_user["id"],
        invitee_username=invitation_data.invitee_username,
        role=invitation_data.role,
    )


@router.get(
    "/workspaces/{workspace_id}/invitations",
    response_model=WorkspaceInvitationList,
)
def list_workspace_invitations(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    List all invitations for a workspace (admin only)

    - **workspace_id**: UUID of the workspace

    Returns a list of all invitations (pending, accepted, declined, expired)
    """
    require_workspace_admin(workspace_id, current_user)

    return workspace_invitation_service.list_workspace_invitations(workspace_id)


@router.delete(
    "/workspaces/{workspace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_invitation(
    workspace_id: str,
    invitation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a pending invitation (admin only)

    - **workspace_id**: UUID of the workspace
    - **invitation_id**: UUID of the invitation

    Returns success message
    """
    require_workspace_admin(workspace_id, current_user)

    workspace_invitation_service.cancel_invitation(invitation_id, current_user["id"])
    return None


@router.get(
    "/invitations/pending",
    response_model=WorkspaceInvitationList,
)
def get_pending_invitations(
    current_user: dict = Depends(get_current_user),
):
    """
    Get all pending invitations for the current user

    Returns a list of pending invitations
    """
    return workspace_invitation_service.list_pending_invitations(current_user["username"])


@router.post(
    "/invitations/{invitation_id}/accept",
    status_code=status.HTTP_200_OK,
)
def accept_invitation(
    invitation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Accept a workspace invitation

    - **invitation_id**: UUID of the invitation

    Returns success message
    """
    return workspace_invitation_service.accept_invitation(invitation_id, current_user["id"])


@router.post(
    "/invitations/{invitation_id}/decline",
    status_code=status.HTTP_200_OK,
)
def decline_invitation(
    invitation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Decline a workspace invitation

    - **invitation_id**: UUID of the invitation

    Returns success message
    """
    return workspace_invitation_service.decline_invitation(invitation_id, current_user["id"])
