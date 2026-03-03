"""Workspace Member service - Business logic for workspace membership operations"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.workspace_member import WorkspaceMember as WorkspaceMemberModel
from server.database.relational_db.models.user import User as UserModel
from server.schemas.workspace_member import (
    WorkspaceMemberDetail,
    WorkspaceMemberList,
    WorkspaceRole,
)
from server.services.audit import (
    AuditEventType,
    AuditRequest,
    ResourceType,
    audit_service,
)
from server.utils import generate_uuid

logger = logging.getLogger(__name__)


class WorkspaceMemberService:
    """Service layer for workspace member business logic"""

    def add_member(
        self, workspace_id: str, user_id: str, role: str, created_by: Optional[str] = None
    ) -> WorkspaceMemberDetail:
        """Add a user to a workspace with a specific role"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if user exists
                user = (
                    session.query(UserModel)
                    .filter(and_(UserModel.id == user_id, UserModel.deleted_at.is_(None)))
                    .first()
                )

                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Check if already a member
                existing_member = (
                    session.query(WorkspaceMemberModel)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if existing_member:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User is already a member of this workspace",
                    )

                # Create new member
                new_member = WorkspaceMemberModel(
                    id=generate_uuid(),
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role=role,
                    created_by=created_by,
                )

                session.add(new_member)
                session.commit()
                session.refresh(new_member)

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_MEMBER,
                        audit_type=AuditEventType.MEMBER_ADDED,
                        audit_resource_id=new_member.id,  # type: ignore[arg-type]
                        created_by=created_by or "",
                        created_at=new_member.joined_at,  # type: ignore[arg-type]
                        audit_information={"workspace_id": workspace_id, "user_id": user_id, "role": role},
                        audit_extra_information="Member added successfully",
                    )
                )

                # Check if user is the workspace creator
                from server.database.relational_db.models.workspace import Workspace as WorkspaceModel

                workspace = session.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
                is_creator = workspace.created_by == user_id if workspace else False

                return WorkspaceMemberDetail(
                    id=new_member.id,  # type: ignore[arg-type]
                    workspace_id=new_member.workspace_id,  # type: ignore[arg-type]
                    user_id=new_member.user_id,  # type: ignore[arg-type]
                    username=user.username,  # type: ignore[arg-type]
                    role=WorkspaceRole(new_member.role),  # type: ignore[arg-type]
                    joined_at=new_member.joined_at,  # type: ignore[arg-type]
                    is_creator=is_creator,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to add member: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add member: {str(e)}",
            )

    def remove_member(self, workspace_id: str, user_id: str, removed_by: Optional[str] = None) -> dict:
        """Remove a user from a workspace (soft delete)"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                member = (
                    session.query(WorkspaceMemberModel)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not member:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Member not found in workspace",
                    )

                # Soft delete
                member.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]

                session.commit()

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_MEMBER,
                        audit_type=AuditEventType.MEMBER_REMOVED,
                        audit_resource_id=member.id,  # type: ignore[arg-type]
                        deleted_by=removed_by or "",
                        deleted_at=member.deleted_at,  # type: ignore[arg-type]
                        audit_information={"workspace_id": workspace_id, "user_id": user_id},
                        audit_extra_information="Member removed successfully",
                    )
                )

                return {"message": "Member removed successfully"}

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to remove member: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove member: {str(e)}",
            )

    def update_member_role(
        self, workspace_id: str, user_id: str, new_role: str, updated_by: Optional[str] = None
    ) -> WorkspaceMemberDetail:
        """Update a member's role in a workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                member = (
                    session.query(WorkspaceMemberModel)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not member:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Member not found in workspace",
                    )

                old_role = member.role
                member.role = new_role  # type: ignore[assignment]

                session.commit()
                session.refresh(member)

                # Get username
                user = session.query(UserModel).filter(UserModel.id == user_id).first()

                # Audit log
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE_MEMBER,
                        audit_type=AuditEventType.MEMBER_ROLE_UPDATED,
                        audit_resource_id=member.id,  # type: ignore[arg-type]
                        updated_by=updated_by or "",
                        updated_at=datetime.now(timezone.utc),
                        audit_information={
                            "workspace_id": workspace_id,
                            "user_id": user_id,
                            "old_role": old_role,
                            "new_role": new_role,
                        },
                        audit_extra_information="Member role updated successfully",
                    )
                )

                # Check if user is the workspace creator
                from server.database.relational_db.models.workspace import Workspace as WorkspaceModel

                workspace = session.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
                is_creator = workspace.created_by == user_id if workspace else False

                return WorkspaceMemberDetail(
                    id=member.id,  # type: ignore[arg-type]
                    workspace_id=member.workspace_id,  # type: ignore[arg-type]
                    user_id=member.user_id,  # type: ignore[arg-type]
                    username=user.username if user else None,  # type: ignore[arg-type]
                    role=WorkspaceRole(member.role),  # type: ignore[arg-type]
                    joined_at=member.joined_at,  # type: ignore[arg-type]
                    is_creator=is_creator,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update member role: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update member role: {str(e)}",
            )

    def list_members(self, workspace_id: str) -> WorkspaceMemberList:
        """List all members of a workspace with user info"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                from server.database.relational_db.models.workspace import Workspace as WorkspaceModel

                # Get workspace creator_id
                workspace = session.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
                creator_id = workspace.created_by if workspace else None

                members = (
                    session.query(WorkspaceMemberModel, UserModel)
                    .join(UserModel, WorkspaceMemberModel.user_id == UserModel.id)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                            UserModel.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

                member_details = [
                    WorkspaceMemberDetail(
                        id=member.id,  # type: ignore[arg-type]
                        workspace_id=member.workspace_id,  # type: ignore[arg-type]
                        user_id=member.user_id,  # type: ignore[arg-type]
                        username=user.username,  # type: ignore[arg-type]
                        role=WorkspaceRole(member.role),  # type: ignore[arg-type]
                        joined_at=member.joined_at,  # type: ignore[arg-type]
                        is_creator=member.user_id == creator_id,  # type: ignore[arg-type]
                    )
                    for member, user in members
                ]

                return WorkspaceMemberList(members=member_details, total=len(member_details))

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to list members: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list members: {str(e)}",
            )

    def get_member(self, workspace_id: str, user_id: str) -> Optional[WorkspaceMemberDetail]:
        """Get a specific member"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                result = (
                    session.query(WorkspaceMemberModel, UserModel)
                    .join(UserModel, WorkspaceMemberModel.user_id == UserModel.id)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not result:
                    return None

                member, user = result

                return WorkspaceMemberDetail(
                    id=member.id,  # type: ignore[arg-type]
                    workspace_id=member.workspace_id,  # type: ignore[arg-type]
                    user_id=member.user_id,  # type: ignore[arg-type]
                    username=user.username,  # type: ignore[arg-type]
                    role=WorkspaceRole(member.role),  # type: ignore[arg-type]
                    joined_at=member.joined_at,  # type: ignore[arg-type]
                )

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get member: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get member: {str(e)}",
            )

    def is_member(self, workspace_id: str, user_id: str) -> bool:
        """Check if a user is a member of a workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                member = (
                    session.query(WorkspaceMemberModel)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                return member is not None

            finally:
                session.close()

        except Exception:
            return False

    def get_member_role(self, workspace_id: str, user_id: str) -> Optional[str]:
        """Get a user's role in a workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                member = (
                    session.query(WorkspaceMemberModel)
                    .filter(
                        and_(
                            WorkspaceMemberModel.workspace_id == workspace_id,
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                return member.role if member else None  # type: ignore[return-value]

            finally:
                session.close()

        except Exception:
            return None

    def get_user_workspaces(self, user_id: str) -> list[str]:
        """Get all workspace IDs for a user"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                members = (
                    session.query(WorkspaceMemberModel.workspace_id)
                    .filter(
                        and_(
                            WorkspaceMemberModel.user_id == user_id,
                            WorkspaceMemberModel.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

                return [member[0] for member in members]

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get user workspaces: {str(e)}")
            return []


# Create singleton instance
workspace_member_service = WorkspaceMemberService()
