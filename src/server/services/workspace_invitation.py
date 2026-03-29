# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Workspace Invitation service - Business logic for workspace invitation operations"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.user import User as UserModel
from server.database.relational_db.models.workspace import Workspace as WorkspaceModel
from server.database.relational_db.models.workspace_invitation import (
    WorkspaceInvitation as WorkspaceInvitationModel,
)
from server.schemas.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitationDetail,
    WorkspaceInvitationList,
    WorkspaceInvitationResponse,
)
from server.services.audit import (
    AuditEventType,
    AuditRequest,
    ResourceType,
    audit_service,
)
from server.services.workspace_member import workspace_member_service
from server.utils import generate_uuid

logger = logging.getLogger(__name__)

# Invitation expiration period in days
INVITATION_EXPIRY_DAYS = 7


class WorkspaceInvitationService:
    """Service layer for workspace invitation business logic"""

    def create_invitation(
        self, workspace_id: str, inviter_id: str, invitee_username: str, role: str
    ) -> WorkspaceInvitationResponse:
        """Create a new workspace invitation (expires in 7 days)"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Verify workspace exists
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(and_(WorkspaceModel.id == workspace_id, WorkspaceModel.deleted_at.is_(None)))
                    .first()
                )

                if not workspace:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workspace not found",
                    )

                # Verify invitee user exists
                invitee = (
                    session.query(UserModel)
                    .filter(and_(UserModel.username == invitee_username, UserModel.deleted_at.is_(None)))
                    .first()
                )

                if not invitee:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User '{invitee_username}' not found",
                    )

                # Check if user is already a member
                if workspace_member_service.is_member(workspace_id, invitee.id):  # type: ignore[arg-type]
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User is already a member of this workspace",
                    )

                # Check for existing pending invitation
                existing_invitation = (
                    session.query(WorkspaceInvitationModel)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.workspace_id == workspace_id,
                            WorkspaceInvitationModel.invitee_username == invitee_username,
                            WorkspaceInvitationModel.status == InvitationStatus.PENDING.value,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if existing_invitation:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A pending invitation already exists for this user",
                    )

                # Create invitation
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(days=INVITATION_EXPIRY_DAYS)

                new_invitation = WorkspaceInvitationModel(
                    id=generate_uuid(),
                    workspace_id=workspace_id,
                    inviter_id=inviter_id,
                    invitee_username=invitee_username,
                    role=role,
                    status=InvitationStatus.PENDING.value,
                    expires_at=expires_at,
                )

                session.add(new_invitation)
                session.commit()
                session.refresh(new_invitation)

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_INVITATION,
                        audit_type=AuditEventType.INVITATION_CREATED,
                        audit_resource_id=new_invitation.id,  # type: ignore[arg-type]
                        created_by=inviter_id,
                        created_at=new_invitation.created_at,  # type: ignore[arg-type]
                        audit_information={
                            "workspace_id": workspace_id,
                            "invitee_username": invitee_username,
                            "role": role,
                            "expires_at": expires_at.isoformat(),
                        },
                        audit_extra_information="Invitation created successfully",
                    )
                )

                return WorkspaceInvitationResponse(id=new_invitation.id)  # type: ignore[arg-type]

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create invitation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create invitation: {str(e)}",
            )

    def get_invitation(self, invitation_id: str) -> Optional[WorkspaceInvitationDetail]:
        """Get a specific invitation"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                result = (
                    session.query(WorkspaceInvitationModel, WorkspaceModel, UserModel)
                    .join(WorkspaceModel, WorkspaceInvitationModel.workspace_id == WorkspaceModel.id)
                    .join(UserModel, WorkspaceInvitationModel.inviter_id == UserModel.id)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.id == invitation_id,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not result:
                    return None

                invitation, workspace, inviter = result

                return WorkspaceInvitationDetail(
                    id=invitation.id,  # type: ignore[arg-type]
                    workspace_id=invitation.workspace_id,  # type: ignore[arg-type]
                    workspace_name=workspace.name,  # type: ignore[arg-type]
                    inviter_id=invitation.inviter_id,  # type: ignore[arg-type]
                    inviter_username=inviter.username,  # type: ignore[arg-type]
                    invitee_username=invitation.invitee_username,  # type: ignore[arg-type]
                    role=invitation.role,  # type: ignore[arg-type]
                    status=InvitationStatus(invitation.status),  # type: ignore[arg-type]
                    created_at=invitation.created_at,  # type: ignore[arg-type]
                    expires_at=invitation.expires_at,  # type: ignore[arg-type]
                    responded_at=invitation.responded_at,  # type: ignore[arg-type]
                )

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get invitation: {str(e)}")
            return None

    def list_pending_invitations(self, username: str) -> WorkspaceInvitationList:
        """Get all pending invitations for a user"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                now = datetime.now(timezone.utc)

                # Mark expired invitations
                self._mark_expired_invitations(session)

                # Get pending invitations
                # Convert now to naive datetime for database comparison
                now_naive = now.replace(tzinfo=None)
                results = (
                    session.query(WorkspaceInvitationModel, WorkspaceModel, UserModel)
                    .join(WorkspaceModel, WorkspaceInvitationModel.workspace_id == WorkspaceModel.id)
                    .join(UserModel, WorkspaceInvitationModel.inviter_id == UserModel.id)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.invitee_username == username,
                            WorkspaceInvitationModel.status == InvitationStatus.PENDING.value,
                            WorkspaceInvitationModel.expires_at > now_naive,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

                invitation_details = [
                    WorkspaceInvitationDetail(
                        id=invitation.id,  # type: ignore[arg-type]
                        workspace_id=invitation.workspace_id,  # type: ignore[arg-type]
                        workspace_name=workspace.name,  # type: ignore[arg-type]
                        inviter_id=invitation.inviter_id,  # type: ignore[arg-type]
                        inviter_username=inviter.username,  # type: ignore[arg-type]
                        invitee_username=invitation.invitee_username,  # type: ignore[arg-type]
                        role=invitation.role,  # type: ignore[arg-type]
                        status=InvitationStatus(invitation.status),  # type: ignore[arg-type]
                        created_at=invitation.created_at,  # type: ignore[arg-type]
                        expires_at=invitation.expires_at,  # type: ignore[arg-type]
                        responded_at=invitation.responded_at,  # type: ignore[arg-type]
                    )
                    for invitation, workspace, inviter in results
                ]

                return WorkspaceInvitationList(invitations=invitation_details, total=len(invitation_details))

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to list pending invitations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list pending invitations: {str(e)}",
            )

    def list_workspace_invitations(self, workspace_id: str) -> WorkspaceInvitationList:
        """Get all invitations for a workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                results = (
                    session.query(WorkspaceInvitationModel, WorkspaceModel, UserModel)
                    .join(WorkspaceModel, WorkspaceInvitationModel.workspace_id == WorkspaceModel.id)
                    .join(UserModel, WorkspaceInvitationModel.inviter_id == UserModel.id)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.workspace_id == workspace_id,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

                invitation_details = [
                    WorkspaceInvitationDetail(
                        id=invitation.id,  # type: ignore[arg-type]
                        workspace_id=invitation.workspace_id,  # type: ignore[arg-type]
                        workspace_name=workspace.name,  # type: ignore[arg-type]
                        inviter_id=invitation.inviter_id,  # type: ignore[arg-type]
                        inviter_username=inviter.username,  # type: ignore[arg-type]
                        invitee_username=invitation.invitee_username,  # type: ignore[arg-type]
                        role=invitation.role,  # type: ignore[arg-type]
                        status=InvitationStatus(invitation.status),  # type: ignore[arg-type]
                        created_at=invitation.created_at,  # type: ignore[arg-type]
                        expires_at=invitation.expires_at,  # type: ignore[arg-type]
                        responded_at=invitation.responded_at,  # type: ignore[arg-type]
                    )
                    for invitation, workspace, inviter in results
                ]

                return WorkspaceInvitationList(invitations=invitation_details, total=len(invitation_details))

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to list workspace invitations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list workspace invitations: {str(e)}",
            )

    def accept_invitation(self, invitation_id: str, user_id: str) -> dict:
        """Accept an invitation and create workspace membership"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Get invitation with user info
                result = (
                    session.query(WorkspaceInvitationModel, UserModel)
                    .join(UserModel, UserModel.id == user_id)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.id == invitation_id,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Invitation not found",
                    )

                invitation, user = result

                # Verify invitation is for this user
                if invitation.invitee_username != user.username:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="This invitation is not for you",
                    )

                # Check if already accepted/declined
                if invitation.status != InvitationStatus.PENDING.value:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Invitation has already been {invitation.status}",
                    )

                # Check if expired
                now = datetime.now(timezone.utc)
                # Make expires_at timezone-aware if it's naive
                expires_at = (
                    invitation.expires_at
                    if invitation.expires_at.tzinfo
                    else invitation.expires_at.replace(tzinfo=timezone.utc)
                )  # type: ignore[union-attr]
                if expires_at < now:
                    invitation.status = InvitationStatus.EXPIRED.value  # type: ignore[assignment]
                    session.commit()
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Invitation has expired",
                    )

                # Update invitation status
                invitation.status = InvitationStatus.ACCEPTED.value  # type: ignore[assignment]
                invitation.responded_at = now  # type: ignore[assignment]
                session.commit()

                # Create workspace membership
                workspace_member_service.add_member(
                    workspace_id=invitation.workspace_id,  # type: ignore[arg-type]
                    user_id=user_id,
                    role=invitation.role,  # type: ignore[arg-type]
                    created_by=user_id,
                )

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_INVITATION,
                        audit_type=AuditEventType.INVITATION_ACCEPTED,
                        audit_resource_id=invitation.id,  # type: ignore[arg-type]
                        updated_by=user_id,
                        updated_at=now,
                        audit_information={
                            "workspace_id": invitation.workspace_id,
                            "user_id": user_id,
                            "role": invitation.role,
                        },
                        audit_extra_information="Invitation accepted",
                    )
                )

                # Get workspace name for response
                from server.database.relational_db.models.workspace import Workspace as WorkspaceModel

                workspace = session.query(WorkspaceModel).filter(WorkspaceModel.id == invitation.workspace_id).first()

                return {
                    "message": "Invitation accepted successfully",
                    "workspace_id": invitation.workspace_id,
                    "workspace_name": workspace.name if workspace else "Unknown",  # type: ignore[union-attr]
                    "assigned_role": invitation.role,
                }

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to accept invitation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to accept invitation: {str(e)}",
            )

    def decline_invitation(self, invitation_id: str, user_id: str) -> dict:
        """Decline an invitation"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Get invitation with user info
                result = (
                    session.query(WorkspaceInvitationModel, UserModel)
                    .join(UserModel, UserModel.id == user_id)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.id == invitation_id,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Invitation not found",
                    )

                invitation, user = result

                # Verify invitation is for this user
                if invitation.invitee_username != user.username:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="This invitation is not for you",
                    )

                # Check if already accepted/declined
                if invitation.status != InvitationStatus.PENDING.value:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Invitation has already been {invitation.status}",
                    )

                # Update invitation status
                now = datetime.now(timezone.utc)
                invitation.status = InvitationStatus.DECLINED.value  # type: ignore[assignment]
                invitation.responded_at = now  # type: ignore[assignment]
                session.commit()

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_INVITATION,
                        audit_type=AuditEventType.INVITATION_DECLINED,
                        audit_resource_id=invitation.id,  # type: ignore[arg-type]
                        updated_by=user_id,
                        updated_at=now,
                        audit_information={
                            "workspace_id": invitation.workspace_id,
                            "user_id": user_id,
                        },
                        audit_extra_information="Invitation declined",
                    )
                )

                return {"message": "Invitation declined"}

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to decline invitation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to decline invitation: {str(e)}",
            )

    def cancel_invitation(self, invitation_id: str, canceller_id: str) -> dict:
        """Cancel a pending invitation (admin only)"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                invitation = (
                    session.query(WorkspaceInvitationModel)
                    .filter(
                        and_(
                            WorkspaceInvitationModel.id == invitation_id,
                            WorkspaceInvitationModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not invitation:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Invitation not found",
                    )

                # Check if already processed
                if invitation.status != InvitationStatus.PENDING.value:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Invitation has already been {invitation.status}",
                    )

                # Soft delete the invitation
                now = datetime.now(timezone.utc)
                invitation.deleted_at = now  # type: ignore[assignment]
                session.commit()

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_INVITATION,
                        audit_type=AuditEventType.INVITATION_CANCELLED,
                        audit_resource_id=invitation.id,  # type: ignore[arg-type]
                        deleted_by=canceller_id,
                        deleted_at=now,
                        audit_information={
                            "workspace_id": invitation.workspace_id,
                            "invitee_username": invitation.invitee_username,
                        },
                        audit_extra_information="Invitation cancelled",
                    )
                )

                return {"message": "Invitation cancelled"}

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel invitation: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel invitation: {str(e)}",
            )

    def _mark_expired_invitations(self, session) -> None:
        """Mark expired invitations (helper method for internal use)"""
        try:
            now = datetime.now(timezone.utc)
            # Convert now to naive datetime for database comparison
            now_naive = now.replace(tzinfo=None)

            expired_invitations = (
                session.query(WorkspaceInvitationModel)
                .filter(
                    and_(
                        WorkspaceInvitationModel.status == InvitationStatus.PENDING.value,
                        WorkspaceInvitationModel.expires_at < now_naive,
                        WorkspaceInvitationModel.deleted_at.is_(None),
                    )
                )
                .all()
            )

            for invitation in expired_invitations:
                invitation.status = InvitationStatus.EXPIRED.value  # type: ignore[assignment]
                invitation.responded_at = now  # type: ignore[assignment]

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_INVITATION,
                        audit_type=AuditEventType.INVITATION_EXPIRED,
                        audit_resource_id=invitation.id,  # type: ignore[arg-type]
                        updated_at=now,
                        audit_information={
                            "workspace_id": invitation.workspace_id,
                            "invitee_username": invitation.invitee_username,
                        },
                        audit_extra_information="Invitation expired automatically",
                    )
                )

            if expired_invitations:
                session.commit()

        except Exception as e:
            logger.error(f"Failed to mark expired invitations: {str(e)}")

    def expire_old_invitations(self) -> dict:
        """Public method to expire old invitations (can be called by cron job)"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                self._mark_expired_invitations(session)
                return {"message": "Expired invitations processed"}

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to expire old invitations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to expire old invitations: {str(e)}",
            )


# Create singleton instance
workspace_invitation_service = WorkspaceInvitationService()
