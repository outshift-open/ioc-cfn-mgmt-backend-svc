"""Cognitive Fabric Node service - Business logic for Cognitive Fabric Node operations"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognitive_fabric_node import (
    CognitiveFabricNode as CognitiveFabricNodeModel,
)
from server.database.relational_db.models.workspace import Workspace as WorkspaceModel
from server.database.relational_db.models.cognitive_agent import CognitiveAgent
from server.schemas.cognitive_fabric_node import (
    CognitiveFabricNodeHeartbeatResponse,
    CognitiveFabricNodeList,
    CognitiveFabricNodeListItem,
    CognitiveFabricNodeRegisterRequest,
    CognitiveFabricNodeResponse,
    CognitiveFabricNodeStatus,
    CognitiveFabricNodeUpdateRequest,
)
from server.services.audit import (
    AuditEventType,
    AuditRequest,
    ResourceType,
    audit_service,
)
from server.services.cognitive_engine import cognitive_engine_service
from server.services.memory_provider import memory_provider_service
from server.services.multi_agentic_system import multi_agentic_system_service
from server.services.workspace import workspace_service


class CognitiveFabricNodeService:
    """Service layer for Cognitive Fabric Node business logic"""

    def _get_workspace_ids(self, session, cfn_id: str) -> List[str]:
        """Get all workspace IDs associated with a CFN (workspaces that reference this CFN)"""
        workspaces = (
            session.query(WorkspaceModel.id)
            .filter(WorkspaceModel.cfn_id == cfn_id, WorkspaceModel.deleted_at.is_(None))
            .all()
        )
        return [ws.id for ws in workspaces]

    def update_config_for_workspace(self, workspace_id: str) -> None:
        """
        Update config_timestamp and regenerate config for all CFNs serving this workspace.

        Called when workspace resources change (MAS, etc.)

        Args:
            workspace_id: ID of the workspace whose resources changed
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the workspace and its CFN
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(WorkspaceModel.id == workspace_id, WorkspaceModel.deleted_at.is_(None))
                    .first()
                )

                if not workspace or not workspace.cfn_id:
                    return  # No CFN associated, nothing to update

                # Get the CFN
                cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(CognitiveFabricNodeModel.cfn_id == workspace.cfn_id)
                    .first()
                )

                if cfn:
                    now = datetime.now(timezone.utc)
                    cfn.config_timestamp = now

                    # Regenerate config
                    workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
                    cfn.config = self.generate_config(cfn.cfn_id, workspace_ids, cfn.cfn_config, now)

                    session.commit()

            finally:
                session.close()

        except Exception:
            # Silently fail to avoid breaking the calling operation
            pass

    def update_config_for_all_cfns(self) -> None:
        """
        Update config_timestamp and regenerate config for all CFNs.

        Called when global resources change (cognitive agents, memory providers, etc.)
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Get all non-deleted CFNs
                cfns = (
                    session.query(CognitiveFabricNodeModel).filter(CognitiveFabricNodeModel.deleted_at.is_(None)).all()
                )

                now = datetime.now(timezone.utc)
                for cfn in cfns:
                    cfn.config_timestamp = now

                    # Regenerate config
                    workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
                    cfn.config = self.generate_config(cfn.cfn_id, workspace_ids, cfn.cfn_config, now)

                session.commit()

            finally:
                session.close()

        except Exception:
            # Silently fail to avoid breaking the calling operation
            pass

    def create(self, cfn_data: CognitiveFabricNodeRegisterRequest, user_id: str) -> CognitiveFabricNodeResponse:
        """
        Create a new Cognitive Fabric Node or refresh an active one

        CFN nodes are like IoT devices - they always call this endpoint.
        The service handles 3 scenarios:
        1. New CFN: Create new CFN entry with generated UUID
        2. Active CFN reconnection: Refresh config (allows reboot/reconciliation)
        3. Disabled CFN: Return 403 Forbidden (requires manual re-enable)

        Workspace association is done during workspace creation.

        Args:
            cfn_data: CFN registration data (cfn_name, cfn_config)
            user_id: User creating the CFN

        Returns:
            CognitiveFabricNodeResponse with config

        Raises:
            HTTPException: 409 if name conflict, 403 if disabled
        """

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if cfn_name exists (only among non-deleted CFNs)
                existing_cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing_cfn:
                    # Scenario 1: CFN is disabled (but not deleted)
                    if not existing_cfn.enabled:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="CFN node has been disabled. Contact workspace admin to re-enable it first.",
                        )

                    # Scenario 2: CFN is active - Allow reboot/reconnection (refresh config)
                    return self._refresh_cfn(session, existing_cfn, cfn_data, user_id)

                # Scenario 3: New CFN - Create new entry with generated UUID
                cfn_id = str(uuid.uuid4())

                # Create new CFN record with offline status
                now = datetime.now(timezone.utc)

                # Generate config (no workspaces initially)
                config = self.generate_config(cfn_id, [], cfn_data.cfn_config, now)

                new_cfn = CognitiveFabricNodeModel(
                    cfn_id=cfn_id,
                    cfn_name=cfn_data.cfn_name,
                    cfn_config=cfn_data.cfn_config,
                    config=config,
                    status=CognitiveFabricNodeStatus.OFFLINE.value,
                    enabled=True,
                    last_seen=now,
                    config_timestamp=now,
                    ip_address=cfn_data.ip_address,
                    port=str(cfn_data.port) if cfn_data.port else None,
                    created_by=user_id,
                )

                session.add(new_cfn)
                session.flush()

                session.commit()
                session.refresh(new_cfn)

                # New CFN has no workspace associations yet
                response = CognitiveFabricNodeResponse(
                    cfn_id=new_cfn.cfn_id,
                    workspace_ids=[],
                    cfn_name=new_cfn.cfn_name,
                    config=new_cfn.config,
                    status=CognitiveFabricNodeStatus(new_cfn.status),
                    last_seen=new_cfn.last_seen,
                    enabled=new_cfn.enabled,
                    ip_address=new_cfn.ip_address,
                    port=int(new_cfn.port) if new_cfn.port else None,
                    created_at=new_cfn.created_at,
                    updated_at=new_cfn.updated_at,
                    created_by=new_cfn.created_by,
                    updated_by=new_cfn.updated_by,
                )

                # Audit logging
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                        audit_type=AuditEventType.RESOURCE_CREATED,
                        audit_resource_id=new_cfn.cfn_id,
                        created_by=user_id,
                        audit_information=cfn_data.model_dump(),
                        audit_extra_information="CFN created successfully",
                        created_at=new_cfn.created_at,
                    )
                )

                return response

            except IntegrityError as e:
                session.rollback()
                error_str = str(e)
                if "idx_cfn_name_unique" in error_str:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.cfn_name}' already exists",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database integrity error: {error_str}",
                )
            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to register CFN: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register CFN: {str(e)}",
            )

    def _reenable_cfn(
        self,
        session,
        cfn: CognitiveFabricNodeModel,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeResponse:
        """
        Re-enable a disabled/de-registered CFN node (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (disabled/deleted)
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitiveFabricNodeResponse with config

        Raises:
            HTTPException: 409 if name conflict
        """
        # Check if cfn_name conflicts with another active CFN (globally unique)
        if cfn_data.cfn_name != cfn.cfn_name:
            existing_name = (
                session.query(CognitiveFabricNodeModel)
                .filter(
                    CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                    CognitiveFabricNodeModel.cfn_id != cfn_data.cfn_id,
                    CognitiveFabricNodeModel.deleted_at.is_(None),
                )
                .first()
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CFN with name '{cfn_data.cfn_name}' already exists",
                )

        # Re-activate the CFN with offline status
        now = datetime.now(timezone.utc)
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
        cfn.last_seen = now
        cfn.enabled = True
        cfn.deleted_at = None
        cfn.updated_at = now
        cfn.updated_by = user_id

        # Regenerate config with existing workspace associations
        workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
        cfn.config = self.generate_config(cfn.cfn_id, workspace_ids, cfn.cfn_config, now)
        cfn.config_timestamp = now  # Config regenerated

        session.commit()
        session.refresh(cfn)

        response = CognitiveFabricNodeResponse(
            cfn_id=cfn.cfn_id,
            workspace_ids=workspace_ids,
            cfn_name=cfn.cfn_name,
            config=cfn.config,
            status=CognitiveFabricNodeStatus(cfn.status),
            last_seen=cfn.last_seen,
            enabled=cfn.enabled,
            ip_address=cfn.ip_address,
            port=int(cfn.port) if cfn.port else None,
            created_at=cfn.created_at,
            updated_at=cfn.updated_at,
            created_by=cfn.created_by,
            updated_by=cfn.updated_by,
        )

        # Audit logging
        audit_service.create_audit(
            AuditRequest(
                resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                audit_type=AuditEventType.RESOURCE_CREATED,
                audit_resource_id=cfn.cfn_id,
                created_by=user_id,
                audit_information=cfn_data.model_dump(),
                audit_extra_information="CFN re-enabled via registration",
                created_at=cfn.updated_at,
            )
        )

        return response

    def _refresh_cfn(
        self,
        session,
        cfn: CognitiveFabricNodeModel,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeResponse:
        """
        Refresh an active CFN node during reboot/reconnection (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (active, found by name)
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitiveFabricNodeResponse with config
        """
        # Update CFN config and refresh (keep existing workspace associations and status)
        # Name is already validated (cfn was found by this name)
        now = datetime.now(timezone.utc)
        cfn.cfn_config = cfn_data.cfn_config
        # Update ip_address and port if provided
        if cfn_data.ip_address is not None:
            cfn.ip_address = cfn_data.ip_address
        if cfn_data.port is not None:
            cfn.port = str(cfn_data.port)
        # Keep existing status (don't reset to offline on refresh)
        cfn.last_seen = now
        cfn.updated_at = now
        cfn.updated_by = user_id

        workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
        cfn.config = self.generate_config(cfn.cfn_id, workspace_ids, cfn.cfn_config)
        cfn.config_timestamp = now  # Config regenerated

        session.commit()
        session.refresh(cfn)

        response = CognitiveFabricNodeResponse(
            cfn_id=cfn.cfn_id,
            workspace_ids=workspace_ids,
            cfn_name=cfn.cfn_name,
            config=cfn.config,
            status=CognitiveFabricNodeStatus(cfn.status),
            last_seen=cfn.last_seen,
            enabled=cfn.enabled,
            ip_address=cfn.ip_address,
            port=int(cfn.port) if cfn.port else None,
            created_at=cfn.created_at,
            updated_at=cfn.updated_at,
            created_by=cfn.created_by,
            updated_by=cfn.updated_by,
        )

        # Audit logging
        audit_service.create_audit(
            AuditRequest(
                resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                audit_type=AuditEventType.RESOURCE_UPDATED,
                audit_resource_id=cfn.cfn_id,
                updated_by=user_id,
                audit_information=cfn_data.model_dump(),
                audit_extra_information="CFN refreshed during reconnection/reboot",
                updated_at=cfn.updated_at,
            )
        )

        return response

    def update(
        self, cfn_id: str, cfn_data: CognitiveFabricNodeUpdateRequest, user_id: str
    ) -> CognitiveFabricNodeResponse:
        """
        Update Cognitive Fabric Node

        Args:
            cfn_id: CFN identifier (immutable)
            cfn_data: Update data
            user_id: User performing update

        Returns:
            CognitiveFabricNodeResponse with updated information

        Raises:
            HTTPException: 404 if not found, 409 if name conflict
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN
                cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        CognitiveFabricNodeModel.cfn_id == cfn_id,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Update cfn_name if provided (check global uniqueness)
                if cfn_data.cfn_name is not None:
                    existing_name = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(
                            CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                            CognitiveFabricNodeModel.cfn_id != cfn_id,
                            CognitiveFabricNodeModel.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if existing_name:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"CFN with name '{cfn_data.cfn_name}' already exists",
                        )
                    cfn.cfn_name = cfn_data.cfn_name

                # Update config if provided
                config_changed = False
                if cfn_data.cfn_config is not None:
                    cfn.cfn_config = cfn_data.cfn_config
                    config_changed = True

                # Update ip_address and port if provided
                if cfn_data.ip_address is not None:
                    cfn.ip_address = cfn_data.ip_address
                if cfn_data.port is not None:
                    cfn.port = str(cfn_data.port)

                # Regenerate config
                workspace_ids = self._get_workspace_ids(session, cfn_id)

                # Update metadata
                now = datetime.now(timezone.utc)
                cfn.updated_at = now
                cfn.updated_by = user_id

                # Update config_timestamp if config changed
                if config_changed or cfn_data.cfn_name is not None:
                    cfn.config_timestamp = now

                # Generate config with timestamp
                cfn.config = self.generate_config(cfn_id, workspace_ids, cfn.cfn_config, cfn.config_timestamp)

                session.commit()
                session.refresh(cfn)

                response = CognitiveFabricNodeResponse(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    config=cfn.config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
                )

                # Audit logging
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                        audit_type=AuditEventType.RESOURCE_UPDATED,
                        audit_resource_id=cfn_id,
                        updated_by=user_id,
                        audit_information=cfn_data.model_dump(),
                        audit_extra_information="CFN updated successfully",
                        updated_at=cfn.updated_at,
                    )
                )

                return response

            except IntegrityError as e:
                session.rollback()
                if "idx_cfn_name_unique" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.cfn_name}' already exists",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database integrity error: {str(e)}",
                )
            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update CFN: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update CFN: {str(e)}",
            )

    def disable(self, cfn_id: str, user_id: str) -> CognitiveFabricNodeResponse:
        """
        Disable Cognitive Fabric Node (soft disable)

        Disabling a CFN stops heartbeats and prepares it for deletion.
        The CFN ID cannot be reused while in disabled state.
        A disabled CFN can be re-enabled via the enable endpoint.

        Args:
            cfn_id: CFN identifier
            user_id: User performing disable operation

        Returns:
            CognitiveFabricNodeResponse with updated information

        Raises:
            HTTPException: 404 if not found, 400 if already disabled
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN (only active ones)
                cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        CognitiveFabricNodeModel.cfn_id == cfn_id,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Check if already disabled
                if not cfn.enabled:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CFN node is already disabled",
                    )

                # Disable the CFN (soft disable, no deleted_at)
                cfn.enabled = False
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                session.commit()
                session.refresh(cfn)

                # Get associated workspace IDs
                workspace_ids = self._get_workspace_ids(session, cfn_id)

                response = CognitiveFabricNodeResponse(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    config=cfn.config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
                )

                # Audit logging
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                        audit_type=AuditEventType.RESOURCE_UPDATED,
                        audit_resource_id=cfn_id,
                        updated_by=user_id,
                        audit_information={},
                        audit_extra_information="CFN disabled (soft disable, prepares for deletion)",
                        updated_at=cfn.updated_at,
                    )
                )

                return response

            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to disable CFN: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to disable CFN: {str(e)}",
            )

    def delete(self, cfn_id: str, user_id: str) -> None:
        """
        Delete Cognitive Fabric Node (hard delete)

        Deleting a CFN marks it as deleted in the database.
        The CFN ID can be reused to create a new CFN node after deletion.
        A CFN must be disabled before it can be deleted.

        Args:
            cfn_id: CFN identifier
            user_id: User performing deletion

        Raises:
            HTTPException: 404 if not found, 400 if not disabled
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN (including disabled ones, but not already deleted)
                cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        CognitiveFabricNodeModel.cfn_id == cfn_id,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Check if CFN is disabled first
                if cfn.enabled:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CFN node must be disabled before it can be deleted. Please disable it first.",
                    )

                # Mark as deleted (hard delete marker - ID can be reused)
                cfn.deleted_at = datetime.now(timezone.utc)
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                # Note: Workspaces referencing this CFN will have their cfn_id set to this value
                # They should be updated or reassigned before deleting the CFN

                session.commit()

                # Audit logging
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                        audit_type=AuditEventType.RESOURCE_DELETED,
                        audit_resource_id=cfn_id,
                        updated_by=user_id,
                        audit_information={},
                        audit_extra_information="CFN deleted (ID can be reused)",
                    )
                )

            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to de-register CFN: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to de-register CFN: {str(e)}",
            )

    def enable(self, cfn_id: str, user_id: str) -> CognitiveFabricNodeResponse:
        """
        Manually re-enable a disabled/de-registered CFN node

        This is a manual admin operation to re-enable a disabled CFN.
        After enabling, the CFN can call /register to reconnect.

        Args:
            cfn_id: CFN identifier
            user_id: User performing the enable operation

        Returns:
            CognitiveFabricNodeResponse with updated information

        Raises:
            HTTPException: 404 if not found, 400 if already enabled
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN (including disabled ones)
                cfn = session.query(CognitiveFabricNodeModel).filter(CognitiveFabricNodeModel.cfn_id == cfn_id).first()

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Check if already enabled
                if cfn.enabled and cfn.deleted_at is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CFN node is already enabled",
                    )

                # Re-enable the CFN
                cfn.enabled = True
                cfn.deleted_at = None
                cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                session.commit()
                session.refresh(cfn)

                # Get associated workspace IDs
                workspace_ids = self._get_workspace_ids(session, cfn_id)

                response = CognitiveFabricNodeResponse(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    config=cfn.config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
                )

                # Audit logging
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                        audit_type=AuditEventType.RESOURCE_UPDATED,
                        audit_resource_id=cfn_id,
                        updated_by=user_id,
                        audit_information={},
                        audit_extra_information="CFN manually re-enabled by admin",
                        updated_at=cfn.updated_at,
                    )
                )

                return response

            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to enable CFN: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enable CFN: {str(e)}",
            )

    def heartbeat(self, cfn_id: str) -> CognitiveFabricNodeHeartbeatResponse:
        """
        Update CFN heartbeat

        Args:
            cfn_id: CFN identifier

        Returns:
            CognitiveFabricNodeHeartbeatResponse with status, last_seen, and config_timestamp

        Raises:
            HTTPException: 404 if not found, 403 if blocked
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN
                cfn = session.query(CognitiveFabricNodeModel).filter(CognitiveFabricNodeModel.cfn_id == cfn_id).first()

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Check if deleted (hard deleted)
                if cfn.deleted_at is not None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node has been deleted and cannot send heartbeats",
                    )

                # Check if disabled (soft disabled)
                if not cfn.enabled:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "CFN node is disabled and cannot send heartbeats. "
                            "Contact workspace admin to re-enable it."
                        ),
                    )

                # Update last_seen
                cfn.last_seen = datetime.now(timezone.utc)

                # If currently offline, mark as online
                if cfn.status == CognitiveFabricNodeStatus.OFFLINE.value:
                    cfn.status = CognitiveFabricNodeStatus.ONLINE.value

                session.commit()
                session.refresh(cfn)

                return CognitiveFabricNodeHeartbeatResponse(
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    config_timestamp=cfn.config_timestamp,
                )

            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process heartbeat: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process heartbeat: {str(e)}",
            )

    def list(self, workspace_id: Optional[str] = None, status_filter: Optional[str] = None) -> CognitiveFabricNodeList:
        """
        List all Cognitive Fabric Nodes, optionally filtered by workspace

        Returns all CFNs (enabled and disabled). Deleted CFNs are never included.

        Args:
            workspace_id: Optional workspace filter (filters to CFN assigned to that workspace)
            status_filter: Optional status filter (online, offline, blocked)

        Returns:
            CognitiveFabricNodeList with nodes and total count

        Raises:
            HTTPException: 404 if workspace_id provided but not found
        """
        # Validate workspace exists if filter provided
        if workspace_id and not workspace_service.exists(workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Base query - exclude only deleted CFNs
                query = session.query(CognitiveFabricNodeModel).filter(
                    CognitiveFabricNodeModel.deleted_at.is_(None),
                )

                # Filter by workspace if provided (find CFN assigned to that workspace)
                if workspace_id:
                    # Get the CFN ID for this workspace
                    workspace = (
                        session.query(WorkspaceModel)
                        .filter(WorkspaceModel.id == workspace_id, WorkspaceModel.deleted_at.is_(None))
                        .first()
                    )
                    if workspace and workspace.cfn_id:
                        query = query.filter(CognitiveFabricNodeModel.cfn_id == workspace.cfn_id)
                    else:
                        # Workspace has no CFN assigned, return empty list
                        return CognitiveFabricNodeList(nodes=[], total=0)

                # Apply status filter if provided
                if status_filter:
                    query = query.filter(CognitiveFabricNodeModel.status == status_filter)

                cfns = query.all()

                node_list = []
                for cfn in cfns:
                    node_list.append(
                        CognitiveFabricNodeListItem(
                            cfn_id=cfn.cfn_id,
                            cfn_name=cfn.cfn_name,
                            status=CognitiveFabricNodeStatus(cfn.status),
                            last_seen=cfn.last_seen,
                            enabled=cfn.enabled,
                            created_at=cfn.created_at,
                        )
                    )

                return CognitiveFabricNodeList(nodes=node_list, total=len(node_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list CFN nodes: {str(e)}",
            )

    def get(self, cfn_id: str) -> CognitiveFabricNodeResponse:
        """
        Get detailed Cognitive Fabric Node information

        Args:
            cfn_id: CFN identifier

        Returns:
            CognitiveFabricNodeResponse with full information

        Raises:
            HTTPException: 404 if not found
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        CognitiveFabricNodeModel.cfn_id == cfn_id,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Get associated workspace IDs
                workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)

                # Get config to ensure it's fetched from the latest data
                cfn.cfn_config = self.generate_config(cfn.cfn_id, workspace_ids, cfn.cfn_config)

                return CognitiveFabricNodeResponse(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    config=cfn.cfn_config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve CFN node: {str(e)}",
            )

    def generate_config(
        self, cfn_id: str, workspace_ids: List[str] = None, cfn_config: dict = None, config_timestamp: datetime = None
    ) -> dict:
        """
        Generate configuration for CFN

        Aggregates config from all associated workspaces.

        Args:
            cfn_id: CFN identifier
            workspace_ids: List of workspace IDs (if None, fetches from join table)
            cfn_config: CFN-specific configuration to include in the config
            config_timestamp: Timestamp when config was last modified

        Returns:
            Dictionary with configuration including cfn_config and config_timestamp
        """
        db = RelationalDB()
        session = db.get_session()

        try:
            if workspace_ids is None:
                workspace_ids = self._get_workspace_ids(session, cfn_id)

            workspaces_payload = []
            for ws_id in workspace_ids:
                # Fetch workspace directly from DB to avoid permission checks
                workspace = (
                    session.query(WorkspaceModel)
                    .filter(
                        WorkspaceModel.id == ws_id,
                        WorkspaceModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not workspace:
                    continue

                workspace_name = workspace.name

                workspace_obj = {
                    "workspace_id": ws_id,
                    "workspace_name": workspace_name,
                    "multi_agentic_systems": [],
                    "cognitive_agents": [],
                    "cognitive_engines": [],
                    "policies": [],
                }

                # Get Multi-Agentic Systems for this workspace
                try:
                    mas_systems = multi_agentic_system_service.list(ws_id).systems
                    workspace_obj["multi_agentic_systems"] = [system.model_dump(mode="json") for system in mas_systems]
                except Exception:
                    pass

                # Get Cognitive Agents for this workspace (global/built-in defaults)
                try:
                    db_agents = RelationalDB()
                    session_agents = db_agents.get_session()
                    try:
                        agents = (
                            session_agents.query(CognitiveAgent)
                            .filter(CognitiveAgent.enabled == True)  # noqa: E712
                            .all()
                        )
                        workspace_obj["cognitive_agents"] = [
                            {
                                "cognitive_agent_id": agent.cognitive_agent_id,
                                "name": agent.cognitive_agent_name,
                                "description": agent.description,
                                "enabled": agent.enabled,
                                "config": agent.config or {},
                            }
                            for agent in agents
                        ]
                    finally:
                        session_agents.close()
                except Exception:
                    pass

                # Get Cognitive Engines for this workspace - Not included for March 2026
                try:
                    engines = cognitive_engine_service.list(ws_id).engines
                    workspace_obj["cognitive_engines"] = [
                        {
                            "cognitive_engine_id": engine.cognitive_engine_id,
                            "name": engine.cognitive_engine_name,
                            "enabled": engine.enabled,
                            "config": engine.config or {},
                        }
                        for engine in engines
                    ]
                except Exception:
                    pass

                workspaces_payload.append(workspace_obj)

            # Fetch Memory Providers (global, not workspace-scoped)
            try:
                providers = memory_provider_service.list().providers
                providers_payload = [
                    {
                        "memory_provider_id": provider.memory_provider_id,
                        "name": provider.memory_provider_name,
                        "enabled": provider.enabled,
                        "config": provider.config or {},
                    }
                    for provider in providers
                ]
            except Exception:
                providers_payload = []

            return {"workspaces": workspaces_payload, "memory_providers": providers_payload}

        finally:
            session.close()

    def mark_stale_nodes_offline(self, threshold_minutes: int = 2) -> int:
        """
        Background job: Mark nodes offline if last_seen > threshold

        Args:
            threshold_minutes: Minutes since last_seen to mark offline

        Returns:
            Count of nodes marked offline
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                threshold_time = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)

                # Find nodes that are online but haven't sent heartbeat
                stale_nodes = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        and_(
                            CognitiveFabricNodeModel.status == CognitiveFabricNodeStatus.ONLINE.value,
                            CognitiveFabricNodeModel.last_seen < threshold_time,
                            CognitiveFabricNodeModel.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

                count = 0
                for cfn in stale_nodes:
                    cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
                    count += 1

                if count > 0:
                    session.commit()

                return count

            finally:
                session.close()

        except Exception as e:
            # Log error but don't raise - this is a background job
            print(f"Error marking stale CFN nodes offline: {str(e)}")
            return 0


# Singleton instance
cognitive_fabric_node_service = CognitiveFabricNodeService()
