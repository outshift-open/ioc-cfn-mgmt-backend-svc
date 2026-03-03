"""Workspace service - Business logic for workspace operations"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.exc import IntegrityError


from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.multi_agentic_system import MultiAgenticSystem as MASModel
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
from server.schemas.workspace_member import WorkspaceMemberDetail
from server.services.audit import (
    AuditEventType,
    AuditRequest,
    ResourceType,
    audit_service,
)
from server.utils import generate_uuid

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Service layer for workspace business logic"""

    DEFAULT_WORKSPACE_NAME = "Default Workspace"

    def _get_workspace_members(self, session, workspace_id: str, creator_id: str = None) -> list:
        """Get workspace members with user details.

        Args:
            session: Database session
            workspace_id: ID of the workspace
            creator_id: Optional creator ID to mark the creator member

        Returns:
            List of WorkspaceMemberDetail objects
        """
        from server.database.relational_db.models.user import User as UserModel

        # Query workspace members with user details
        members = (
            session.query(
                WorkspaceMemberModel.id,
                WorkspaceMemberModel.workspace_id,
                WorkspaceMemberModel.user_id,
                WorkspaceMemberModel.role,
                WorkspaceMemberModel.joined_at,
                UserModel.username,
            )
            .join(UserModel, WorkspaceMemberModel.user_id == UserModel.id)
            .filter(
                and_(
                    WorkspaceMemberModel.workspace_id == workspace_id,
                    WorkspaceMemberModel.deleted_at.is_(None),
                )
            )
            .all()
        )

        # Convert to WorkspaceMemberDetail objects
        member_details = [
            WorkspaceMemberDetail(
                id=member.id,
                workspace_id=member.workspace_id,
                user_id=member.user_id,
                username=member.username,
                role=member.role,
                joined_at=member.joined_at,
                is_creator=(member.user_id == creator_id) if creator_id else False,
            )
            for member in members
        ]

        return member_details

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

    def create(
        self, workspace_data: WorkspaceCreate, creator_user_id: str, workspace_id: str = None
    ) -> WorkspaceResponse:
        """Create a new workspace

        Args:
            workspace_data: Workspace creation data
            creator_user_id: ID of the user creating the workspace
            workspace_id: Optional hardcoded workspace ID (for admin default workspace only)

        Raises:
            HTTPException: 404 if CFN not found, 400 if CFN required but not provided, 409 on conflict
        """
        from server.database.relational_db.models.cognitive_fabric_node import (
            CognitiveFabricNode as CognitiveFabricNodeModel,
        )

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Validate CFN if provided
                if workspace_data.cfn_id:
                    cfn = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(
                            CognitiveFabricNodeModel.cfn_id == workspace_data.cfn_id,
                            CognitiveFabricNodeModel.deleted_at.is_(None),
                        )
                        .first()
                    )

                    if not cfn:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"CFN with id '{workspace_data.cfn_id}' not found or has been deleted",
                        )

                    if not cfn.enabled:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"CFN '{workspace_data.cfn_id}' is disabled. Please enable it first.",
                        )

                workspace_kwargs = {
                    "name": workspace_data.name,
                    "users": [],  # Legacy field, kept for backwards compatibility
                    "config": workspace_data.config,
                    "created_by": creator_user_id,
                    "cfn_id": workspace_data.cfn_id,
                }

                # Add workspace_id - either provided (for admin default workspace) or generate new one
                workspace_kwargs["id"] = workspace_id if workspace_id else generate_uuid()

                # Check if workspace name already exists for the user to prevent duplicates
                existing_workspace = (
                    session.query(WorkspaceModel)
                    .filter(
                        and_(
                            WorkspaceModel.name == workspace_data.name,
                            WorkspaceModel.created_by == creator_user_id,
                            WorkspaceModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if existing_workspace:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Workspace with name '{workspace_data.name}' already exists",
                    )

                new_workspace = WorkspaceModel(**workspace_kwargs)

                session.add(new_workspace)
                session.flush()

                session.commit()
                session.refresh(new_workspace)

                if workspace_data.cfn_id:
                    from server.services.cognitive_fabric_node import cognitive_fabric_node_service

                    cfn = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(CognitiveFabricNodeModel.cfn_id == workspace_data.cfn_id)
                        .first()
                    )
                    if cfn:
                        now = datetime.now(timezone.utc)
                        cfn.config_timestamp = now
                        workspace_ids = (
                            session.query(WorkspaceModel.id)
                            .filter(WorkspaceModel.cfn_id == workspace_data.cfn_id, WorkspaceModel.deleted_at.is_(None))
                            .all()
                        )
                        ws_ids = [ws.id for ws in workspace_ids]
                        cfn.config = cognitive_fabric_node_service.generate_config(
                            cfn.cfn_id, ws_ids, cfn.cfn_config, now
                        )
                        session.commit()

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
                cfn_info = f" and associated with CFN {workspace_data.cfn_id}" if workspace_data.cfn_id else ""
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE,
                        audit_type=AuditEventType.RESOURCE_CREATED,
                        audit_resource_id=new_workspace.id,  # type: ignore[arg-type]
                        created_by="",  # TODO: get user from apikey
                        created_at=new_workspace.created_at,  # type: ignore[arg-type]
                        audit_information=workspace_data.model_dump(),
                        audit_extra_information=f"Workspace created successfully{cfn_info}",
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

    def list(self, user_id: str, user_role: str) -> WorkspaceList:
        """List workspaces accessible to the user.

        Super admins see all workspaces. Regular users see workspaces where they are:
        - A workspace admin (role='admin' in workspace_member table), OR
        - A workspace viewer (role='viewer' in workspace_member table), OR
        - The creator of the workspace (created_by field)

        Guests (role='guest') are excluded from workspace listings.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                from server.database.relational_db.models.user import User as UserModel

                # Super admins can see all workspaces (future feature)
                if user_role == "super_admin":
                    workspaces = session.query(WorkspaceModel).filter(WorkspaceModel.deleted_at.is_(None)).all()
                else:
                    # Regular users see workspaces where they are workspace admins/viewers OR creators
                    # Get workspaces where user is a workspace admin or viewer
                    member_workspaces = (
                        session.query(WorkspaceModel)
                        .join(
                            WorkspaceMemberModel,
                            and_(
                                WorkspaceMemberModel.workspace_id == WorkspaceModel.id,
                                WorkspaceMemberModel.deleted_at.is_(None),
                            ),
                        )
                        .filter(
                            and_(
                                WorkspaceModel.deleted_at.is_(None),
                                WorkspaceMemberModel.user_id == user_id,
                                WorkspaceMemberModel.role.in_(["admin", "viewer"]),
                            )
                        )
                    )

                    # Get workspaces created by the user
                    created_workspaces = session.query(WorkspaceModel).filter(
                        and_(
                            WorkspaceModel.deleted_at.is_(None),
                            WorkspaceModel.created_by == user_id,
                        )
                    )

                    # Union the two queries and get distinct results
                    workspaces = member_workspaces.union(created_workspaces).all()

                # Get creator usernames for all workspaces
                workspace_ids = [ws.id for ws in workspaces]
                creator_map = {}
                if workspace_ids:
                    creators = (
                        session.query(WorkspaceModel.id, UserModel.username)
                        .outerjoin(UserModel, WorkspaceModel.created_by == UserModel.id)
                        .filter(WorkspaceModel.id.in_(workspace_ids))
                        .all()
                    )
                    creator_map = {ws_id: username for ws_id, username in creators}

                workspace_details = []
                for workspace in workspaces:
                    # Get workspace members
                    members = self._get_workspace_members(session, workspace.id, workspace.created_by)

                    workspace_details.append(
                        WorkspaceDetail(
                            id=workspace.id,  # type: ignore[arg-type]
                            name=workspace.name,  # type: ignore[arg-type]
                            cfn_id=workspace.cfn_id,  # type: ignore[arg-type]
                            created_at=workspace.created_at,  # type: ignore[arg-type]
                            created_by=workspace.created_by,  # type: ignore[arg-type]
                            created_by_username=creator_map.get(workspace.id),  # type: ignore[arg-type]
                            members=members,
                            config=workspace.config,  # type: ignore[arg-type]
                        )
                    )

                return WorkspaceList(workspaces=workspace_details, total=len(workspace_details))

            finally:
                session.close()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list workspaces: {str(e)}",
            )

    def get(self, workspace_id: str, user_id: str = None, user_role: str = None) -> WorkspaceDetail:
        """Get a specific workspace by ID.

        If user_id and user_role are provided, verifies the user has access to the workspace.
        Super admins have access to all workspaces. Regular users must be workspace admins, viewers, or creators.
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

                # Check access if user info is provided
                if user_id and user_role:
                    if user_role != "super_admin":
                        # Check if user is workspace admin or viewer
                        workspace_member = (
                            session.query(WorkspaceMemberModel)
                            .filter(
                                and_(
                                    WorkspaceMemberModel.workspace_id == workspace_id,
                                    WorkspaceMemberModel.user_id == user_id,
                                    WorkspaceMemberModel.role.in_(["admin", "viewer"]),
                                    WorkspaceMemberModel.deleted_at.is_(None),
                                )
                            )
                            .first()
                        )

                        is_creator = workspace.created_by == user_id

                        if not (workspace_member or is_creator):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied: You must be a workspace admin, viewer, or creator",
                            )

                # Get creator username
                from server.database.relational_db.models.user import User as UserModel

                creator_username = None
                if workspace.created_by:
                    creator = session.query(UserModel).filter(UserModel.id == workspace.created_by).first()
                    creator_username = creator.username if creator else None

                # Get workspace members
                members = self._get_workspace_members(session, workspace.id, workspace.created_by)

                return WorkspaceDetail(
                    id=workspace.id,  # type: ignore[arg-type]
                    name=workspace.name,  # type: ignore[arg-type]
                    cfn_id=workspace.cfn_id,  # type: ignore[arg-type]
                    created_at=workspace.created_at,  # type: ignore[arg-type]
                    created_by=workspace.created_by,  # type: ignore[arg-type]
                    created_by_username=creator_username,
                    members=members,
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

    def update(
        self, workspace_id: str, workspace_data: WorkspaceUpdate, user_id: str = None, user_role: str = None
    ) -> WorkspaceDetail:
        """Update a workspace.

        If user_id and user_role are provided, verifies the user has access to the workspace.
        Super admins have access to all workspaces. Regular users must be workspace admins or creators.
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

                # Check access if user info is provided
                if user_id and user_role:
                    if user_role != "super_admin":
                        # Check if user is workspace admin or creator
                        is_workspace_admin = (
                            session.query(WorkspaceMemberModel)
                            .filter(
                                and_(
                                    WorkspaceMemberModel.workspace_id == workspace_id,
                                    WorkspaceMemberModel.user_id == user_id,
                                    WorkspaceMemberModel.role == "admin",
                                    WorkspaceMemberModel.deleted_at.is_(None),
                                )
                            )
                            .first()
                        )

                        is_creator = workspace.created_by == user_id

                        if not (is_workspace_admin or is_creator):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied: You must be a workspace admin or creator",
                            )

                # Update only provided fields
                if workspace_data.name is not None:
                    workspace.name = workspace_data.name  # type: ignore[assignment]

                # Handle CFN reassignment
                old_cfn_id = workspace.cfn_id
                if workspace_data.cfn_id is not None:
                    # Validate new CFN exists and is enabled
                    from server.database.relational_db.models.cognitive_fabric_node import (
                        CognitiveFabricNode as CognitiveFabricNodeModel,
                    )

                    cfn = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(
                            CognitiveFabricNodeModel.cfn_id == workspace_data.cfn_id,
                            CognitiveFabricNodeModel.deleted_at.is_(None),
                        )
                        .first()
                    )

                    if not cfn:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"CFN with id '{workspace_data.cfn_id}' not found or has been deleted",
                        )

                    if not cfn.enabled:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"CFN '{workspace_data.cfn_id}' is disabled. Please enable it first.",
                        )

                    workspace.cfn_id = workspace_data.cfn_id  # type: ignore[assignment]

                workspace.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

                session.commit()
                session.refresh(workspace)

                # Update CFN config_timestamp if workspace's CFN association changed
                if workspace_data.cfn_id is not None and old_cfn_id != workspace_data.cfn_id:
                    from server.database.relational_db.models.cognitive_fabric_node import (
                        CognitiveFabricNode as CognitiveFabricNodeModel,
                    )
                    from server.services.cognitive_fabric_node import cognitive_fabric_node_service

                    now = datetime.now(timezone.utc)

                    # Update old CFN if it existed (workspace removed from it)
                    if old_cfn_id:
                        old_cfn = (
                            session.query(CognitiveFabricNodeModel)
                            .filter(CognitiveFabricNodeModel.cfn_id == old_cfn_id)
                            .first()
                        )
                        if old_cfn:
                            old_cfn.config_timestamp = now
                            # Regenerate config without removed workspace
                            old_workspace_ids = (
                                session.query(WorkspaceModel.id)
                                .filter(WorkspaceModel.cfn_id == old_cfn_id, WorkspaceModel.deleted_at.is_(None))
                                .all()
                            )
                            old_ws_ids = [ws.id for ws in old_workspace_ids]
                            old_cfn.config = cognitive_fabric_node_service.generate_config(
                                old_cfn.cfn_id, old_ws_ids, old_cfn.cfn_config, now
                            )

                    # Update new CFN (workspace added to it)
                    if workspace_data.cfn_id:
                        new_cfn = (
                            session.query(CognitiveFabricNodeModel)
                            .filter(CognitiveFabricNodeModel.cfn_id == workspace_data.cfn_id)
                            .first()
                        )
                        if new_cfn:
                            new_cfn.config_timestamp = now
                            # Regenerate config with added workspace
                            new_workspace_ids = (
                                session.query(WorkspaceModel.id)
                                .filter(
                                    WorkspaceModel.cfn_id == workspace_data.cfn_id, WorkspaceModel.deleted_at.is_(None)
                                )
                                .all()
                            )
                            new_ws_ids = [ws.id for ws in new_workspace_ids]
                            new_cfn.config = cognitive_fabric_node_service.generate_config(
                                new_cfn.cfn_id, new_ws_ids, new_cfn.cfn_config, now
                            )

                    session.commit()

                # Get creator username
                from server.database.relational_db.models.user import User as UserModel

                creator_username = None
                if workspace.created_by:
                    creator = session.query(UserModel).filter(UserModel.id == workspace.created_by).first()
                    creator_username = creator.username if creator else None

                # Get workspace members
                members = self._get_workspace_members(session, workspace.id, workspace.created_by)

                response = WorkspaceDetail(
                    id=workspace.id,  # type: ignore[arg-type]
                    name=workspace.name,  # type: ignore[arg-type]
                    cfn_id=workspace.cfn_id,  # type: ignore[arg-type]
                    created_at=workspace.created_at,  # type: ignore[arg-type]
                    updated_at=workspace.updated_at,  # type: ignore[arg-type]
                    created_by=workspace.created_by,  # type: ignore[arg-type]
                    created_by_username=creator_username,
                    members=members,
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

    def delete(
        self,
        workspace_id: str,
        user_id: str = None,
        user_role: str = None,
        allow_default_delete: bool = False,
    ) -> dict:
        """Delete a workspace (soft delete only).

        If user_id and user_role are provided, verifies the user has access to the workspace.
        Super admins have access to all workspaces. Regular users must be workspace admins or creators.
        Blocks deletion of the Default Workspace unless allow_default_delete is True.
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

                # Block deletion of the Default Workspace (only allow via internal API)
                if (not allow_default_delete) and (workspace.name == self.DEFAULT_WORKSPACE_NAME):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Failed to delete workspace: Default Workspace cannot be deleted",
                    )

                # Check access if user info is provided
                if user_id and user_role:
                    if user_role != "super_admin":
                        # Check if user is workspace admin or creator
                        is_workspace_admin = (
                            session.query(WorkspaceMemberModel)
                            .filter(
                                and_(
                                    WorkspaceMemberModel.workspace_id == workspace_id,
                                    WorkspaceMemberModel.user_id == user_id,
                                    WorkspaceMemberModel.role == "admin",
                                    WorkspaceMemberModel.deleted_at.is_(None),
                                )
                            )
                            .first()
                        )

                        is_creator = workspace.created_by == user_id

                        if not (is_workspace_admin or is_creator):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied: You must be a workspace admin or creator",
                            )

                # Validate dependent objects - soft delete requires no dependencies
                has_deps, found_detail = self._get_dependency_status(session, workspace_id)
                if has_deps:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Workspace has dependent objects. "
                            "Delete all dependent objects before deleting the workspace. "
                            f"Found: {found_detail}."
                        ),
                    )

                workspace.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                message = "Workspace deleted successfully"

                # Track CFN ID before deletion
                deleted_workspace_cfn_id = workspace.cfn_id

                session.commit()

                # Update CFN config_timestamp if workspace was associated with a CFN
                if deleted_workspace_cfn_id:
                    from server.database.relational_db.models.cognitive_fabric_node import (
                        CognitiveFabricNode as CognitiveFabricNodeModel,
                    )
                    from server.services.cognitive_fabric_node import cognitive_fabric_node_service

                    cfn = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(CognitiveFabricNodeModel.cfn_id == deleted_workspace_cfn_id)
                        .first()
                    )
                    if cfn:
                        now = datetime.now(timezone.utc)
                        cfn.config_timestamp = now
                        # Regenerate config without deleted workspace
                        workspace_ids = (
                            session.query(WorkspaceModel.id)
                            .filter(
                                WorkspaceModel.cfn_id == deleted_workspace_cfn_id, WorkspaceModel.deleted_at.is_(None)
                            )
                            .all()
                        )
                        ws_ids = [ws.id for ws in workspace_ids]
                        cfn.config = cognitive_fabric_node_service.generate_config(
                            cfn.cfn_id, ws_ids, cfn.cfn_config, now
                        )
                        session.commit()

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.WORKSPACE,
                        audit_type=AuditEventType.RESOURCE_DELETED,
                        audit_resource_id=workspace_id,
                        deleted_by="",  # TODO: get user from apikey
                        deleted_at=workspace.deleted_at,  # type: ignore[arg-type]
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

    def exists(self, workspace_id: str) -> bool:
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
