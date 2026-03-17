# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter, Depends, HTTPException, status

from server.authn.auth import get_auth_user
from server.schemas.workspace_invitation import (
    WorkspaceInvitationAcceptResponse,
    WorkspaceInvitationCreate,
    WorkspaceInvitationList,
    WorkspaceInvitationResponse,
)
from server.services.workspace_invitation import workspace_invitation_service
from server.services.workspace_member import workspace_member_service

router = APIRouter()


def require_workspace_admin(workspace_id: str, auth_user: dict) -> None:
    """Check if user is an admin of the workspace"""
    # Super admin has access to all workspaces
    if auth_user["role"] == "super_admin":
        return

    # Check workspace membership and role
    member_role = workspace_member_service.get_member_role(workspace_id, auth_user["id"])
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
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a workspace invitation (admin only)

    - **workspace_id**: UUID of the workspace
    - **invitee_username**: Username of user to invite
    - **role**: Role to assign (admin/viewer/guest)

    Returns the UUID of the created invitation
    """
    require_workspace_admin(workspace_id, auth_user)

    return workspace_invitation_service.create_invitation(
        workspace_id=workspace_id,
        inviter_id=auth_user["id"],
        invitee_username=invitation_data.invitee_username,
        role=invitation_data.role,
    )


@router.get(
    "/workspaces/{workspace_id}/invitations",
    response_model=WorkspaceInvitationList,
)
def list_workspace_invitations(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all invitations for a workspace (admin only)

    - **workspace_id**: UUID of the workspace

    Returns a list of all invitations (pending, accepted, declined, expired)
    """
    require_workspace_admin(workspace_id, auth_user)

    return workspace_invitation_service.list_workspace_invitations(workspace_id)


@router.delete(
    "/workspaces/{workspace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_invitation(
    workspace_id: str,
    invitation_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Cancel a pending invitation (admin only)

    - **workspace_id**: UUID of the workspace
    - **invitation_id**: UUID of the invitation

    Returns success message
    """
    require_workspace_admin(workspace_id, auth_user)

    workspace_invitation_service.cancel_invitation(invitation_id, auth_user["id"])
    return None


@router.get(
    "/invitations/pending",
    response_model=WorkspaceInvitationList,
)
def get_pending_invitations(
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get all pending invitations for the current user

    Returns a list of pending invitations
    """
    return workspace_invitation_service.list_pending_invitations(auth_user["username"])


@router.post(
    "/invitations/{invitation_id}/accept",
    response_model=WorkspaceInvitationAcceptResponse,
    status_code=status.HTTP_200_OK,
)
def accept_invitation(
    invitation_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Accept a workspace invitation

    - **invitation_id**: UUID of the invitation

    Returns success message with workspace details and assigned role
    """
    return workspace_invitation_service.accept_invitation(invitation_id, auth_user["id"])


@router.post(
    "/invitations/{invitation_id}/decline",
    status_code=status.HTTP_200_OK,
)
def decline_invitation(
    invitation_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Decline a workspace invitation

    - **invitation_id**: UUID of the invitation

    Returns success message
    """
    return workspace_invitation_service.decline_invitation(invitation_id, auth_user["id"])
