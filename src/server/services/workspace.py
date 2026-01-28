"""Workspace service - Business logic for workspace operations"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.exc import IntegrityError

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.mas import MultiAgenticSystem as MASModel
from server.database.relational_db.models.workspace import Workspace as WorkspaceModel
from server.database.relational_db.models.workspace_member import WorkspaceMember as WorkspaceMemberModel
from server.database.relational_db.models.workspace_invitation import (
    WorkspaceInvitation as WorkspaceInvitationModel,
)
from server.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceList,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from server.services.audit import (
    AuditEventType,
    AuditRequest,
    ResourceType,
    audit_service,
)


class WorkspaceService:
    """Service layer for workspace business logic"""

    DEFAULT_WORKSPACE_NAME = "Default Workspace"

    def _get_dependency_status(self, session, workspace_id: str):
        """Check if workspace has dependent objects before deletion.
        Returns a tuple: (has_dependents: bool, detail: str)
        """
        mas_exists = bool(
            session.query(
                exists().where(and_(MASModel.workspace_id == workspace_id, MASModel.deleted_at.is_(None)))
            ).scalar()
        )

        if not mas_exists:
            return False, ""

        mas_count = (
            session.query(MASModel).filter(MASModel.workspace_id == workspace_id, MASModel.deleted_at.is_(None)).count()
        )

        found_parts = []
        if mas_count > 0:
            found_parts.append(f"{mas_count} MAS")
        return True, ", ".join(found_parts)

    def _purge_dependents(self, session, workspace_id: str):
        """Hard delete all dependent objects for a workspace during internal purge operations"""
        # Delete workspace members
        session.query(WorkspaceMemberModel).filter(WorkspaceMemberModel.workspace_id == workspace_id).delete(
            synchronize_session=False
        )

        # Delete workspace invitations
        session.query(WorkspaceInvitationModel).filter(WorkspaceInvitationModel.workspace_id == workspace_id).delete(
            synchronize_session=False
        )

        # Delete multi-agentic systems
        session.query(MASModel).filter(MASModel.workspace_id == workspace_id).delete(synchronize_session=False)

    def create_workspace(self, workspace_data: WorkspaceCreate, creator_user_id: str) -> WorkspaceResponse:
        """Create a new workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Prevent duplicate active workspace names
                existing = (
                    session.query(WorkspaceModel)
                    .filter(
                        WorkspaceModel.name == workspace_data.name,
                        WorkspaceModel.deleted_at.is_(None),
                    )
                    .first()
                )
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Workspace with name '{workspace_data.name}' already exists",
                    )

                new_workspace = WorkspaceModel(
                    name=workspace_data.name,
                    users=workspace_data.users or [],
                    config=workspace_data.config,
                )

                session.add(new_workspace)
                session.commit()
                session.refresh(new_workspace)

                # Automatically add creator as workspace admin
                from server.services.workspace_member import workspace_member_service

                workspace_member_service.add_member(
                    workspace_id=new_workspace.id,  # type: ignore[arg-type]
                    user_id=creator_user_id,
                    role="admin",
                    created_by=creator_user_id,
                )

                response = WorkspaceResponse(id=new_workspace.id)  # type: ignore[arg-type]

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE,
                        audit_type=AuditEventType.RESOURCE_CREATED,
                        audit_resource_id=new_workspace.id,  # type: ignore[arg-type]
                        created_by="",  # TODO: get user from apikey
                        created_at=new_workspace.created_at,  # type: ignore[arg-type]
                        audit_information=workspace_data.model_dump(),
                        audit_extra_information="Workspace created successfully",
                    )
                )

                return response

            finally:
                session.close()

        except HTTPException:
            raise
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workspace creation failed due to data conflict: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create workspace: {str(e)}",
            )

    def list_workspaces(self) -> WorkspaceList:
        """List all active workspaces"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                workspaces = session.query(WorkspaceModel).filter(WorkspaceModel.deleted_at.is_(None)).all()

                workspace_details = [
                    WorkspaceDetail(
                        id=workspace.id,  # type: ignore[arg-type]
                        name=workspace.name,  # type: ignore[arg-type]
                        created_at=workspace.created_at,  # type: ignore[arg-type]
                        users=workspace.users or [],  # type: ignore[arg-type]
                        config=workspace.config,  # type: ignore[arg-type]
                    )
                    for workspace in workspaces
                ]

                return WorkspaceList(workspaces=workspace_details, total=len(workspace_details))

            finally:
                session.close()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list workspaces: {str(e)}",
            )

    def get_workspace(self, workspace_id: str) -> WorkspaceDetail:
        """Get a specific workspace by ID"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(
                        and_(
                            WorkspaceModel.id == workspace_id,
                            WorkspaceModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not workspace:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workspace not found",
                    )

                return WorkspaceDetail(
                    id=workspace.id,  # type: ignore[arg-type]
                    name=workspace.name,  # type: ignore[arg-type]
                    created_at=workspace.created_at,  # type: ignore[arg-type]
                    users=workspace.users or [],  # type: ignore[arg-type]
                    config=workspace.config,  # type: ignore[arg-type]
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get workspace: {str(e)}",
            )

    def update_workspace(self, workspace_id: str, workspace_data: WorkspaceUpdate) -> WorkspaceDetail:
        """Update a workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(
                        and_(
                            WorkspaceModel.id == workspace_id,
                            WorkspaceModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not workspace:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workspace not found",
                    )

                # Update only provided fields
                if workspace_data.name is not None:
                    workspace.name = workspace_data.name  # type: ignore[assignment]

                workspace.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

                session.commit()
                session.refresh(workspace)

                response = WorkspaceDetail(
                    id=workspace.id,  # type: ignore[arg-type]
                    name=workspace.name,  # type: ignore[arg-type]
                    created_at=workspace.created_at,  # type: ignore[arg-type]
                    updated_at=workspace.updated_at,  # type: ignore[arg-type]
                    users=workspace.users or [],  # type: ignore[arg-type]
                    config=workspace.config,  # type: ignore[arg-type]
                )

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE,
                        audit_type=AuditEventType.RESOURCE_UPDATED,
                        audit_resource_id=workspace_id,
                        updated_by="",  # TODO: get user from apikey
                        updated_at=workspace.updated_at,  # type: ignore[arg-type]
                        audit_information=workspace_data.model_dump(),
                        audit_extra_information="success",
                    )
                )

                return response

            finally:
                session.close()

        except HTTPException:
            raise
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workspace update failed due to data conflict: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update workspace: {str(e)}",
            )

    def delete_workspace(self, workspace_id: str, _purge: bool = False, allow_default_delete: bool = False) -> dict:
        """Delete a workspace (soft delete by default, hard delete if purge=True)
        Blocks deletion of the default workspace.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(
                        and_(
                            WorkspaceModel.id == workspace_id,
                            WorkspaceModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not workspace:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Workspace not found",
                    )

                # Block deletion of the Default Workspace in public paths
                if (not allow_default_delete) and (workspace.name == self.DEFAULT_WORKSPACE_NAME):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Failed to delete workspace: Default Workspace cannot be deleted",
                    )

                # Validate dependent objects only for soft delete; for purge, hard-delete dependents first
                has_deps, found_detail = self._get_dependency_status(session, workspace_id)
                if has_deps and not _purge:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Workspace has dependent objects. "
                            "Delete all dependent objects before deleting the workspace. "
                            f"Found: {found_detail}."
                        ),
                    )

                if _purge:
                    # Hard delete dependents (including soft-deleted ones) to avoid FK violations
                    self._purge_dependents(session, workspace_id)
                    session.delete(workspace)
                    message = "Workspace permanently deleted"
                else:
                    workspace.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                    message = "Workspace deleted successfully"

                session.commit()

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE,
                        audit_type=AuditEventType.RESOURCE_DELETED,
                        audit_resource_id=workspace_id,
                        deleted_by="",  # TODO: get user from apikey
                        deleted_at=workspace.deleted_at,  # type: ignore[arg-type]
                        audit_information={"purge": _purge},
                        audit_extra_information=message,
                    )
                )

                return {"message": message}

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete workspace: {str(e)}",
            )

    def workspace_exists(self, workspace_id: str) -> bool:
        """Check if a workspace exists"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(
                        and_(
                            WorkspaceModel.id == workspace_id,
                            WorkspaceModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                return workspace is not None

            finally:
                session.close()

        except Exception:
            return False


# Create singleton instance
workspace_service = WorkspaceService()
