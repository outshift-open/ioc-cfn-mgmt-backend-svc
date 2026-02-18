"""Cognitive Fabric Node service - Business logic for Cognitive Fabric Node operations"""

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
from server.schemas.cognitive_fabric_node import (
    CognitiveFabricNodeDetail,
    CognitiveFabricNodeHeartbeatResponse,
    CognitiveFabricNodeList,
    CognitiveFabricNodeListItem,
    CognitiveFabricNodeRegisterRequest,
    CognitiveFabricNodeRegisterResponse,
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

    def create(self, cfn_data: CognitiveFabricNodeRegisterRequest, user_id: str) -> CognitiveFabricNodeRegisterResponse:
        """
        Create a new Cognitive Fabric Node or refresh an active one

        CFN nodes are like IoT devices - they always call this endpoint.
        The service handles 4 scenarios:
        1. New CFN: Create new CFN entry
        2. Deleted CFN (ID reuse): Update deleted record to create new CFN with same ID
        3. Active CFN reconnection: Refresh config (allows reboot/reconciliation)
        4. Disabled CFN: Return 403 Forbidden (requires manual re-enable)

        Workspace association is done during workspace creation.

        Args:
            cfn_data: CFN registration data (cfn_id, cfn_name, cfn_config)
            user_id: User creating the CFN

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

        Raises:
            HTTPException: 409 if name/id conflict, 403 if disabled
        """

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if cfn_id exists (including disabled/deleted)
                existing_cfn = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(CognitiveFabricNodeModel.cfn_id == cfn_data.cfn_id)
                    .first()
                )

                if existing_cfn:
                    # Scenario 1: CFN is fully deleted (deleted_at is set) - ID can be reused
                    if existing_cfn.deleted_at is not None:
                        # Check if new name conflicts with another ACTIVE CFN (globally unique)
                        conflicting_name = (
                            session.query(CognitiveFabricNodeModel)
                            .filter(
                                CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                                CognitiveFabricNodeModel.deleted_at.is_(None),
                                CognitiveFabricNodeModel.cfn_id != cfn_data.cfn_id,
                            )
                            .first()
                        )
                        if conflicting_name:
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail=f"CFN with name '{cfn_data.cfn_name}' already exists",
                            )

                        return self._reuse_deleted_cfn(session, existing_cfn, cfn_data, user_id)

                    # Scenario 2a: CFN is disabled (but not deleted) - ID is LOCKED
                    elif not existing_cfn.enabled:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="CFN node has been disabled. Contact workspace admin to re-enable it first.",
                        )

                    # Scenario 2b: CFN is active - Allow reboot/reconnection (refresh config)
                    else:
                        return self._refresh_cfn(session, existing_cfn, cfn_data, user_id)

                # Scenario 3: New CFN - Create new entry
                # Check if cfn_name already exists globally
                existing_name = (
                    session.query(CognitiveFabricNodeModel)
                    .filter(
                        CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )
                if existing_name:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.cfn_name}' already exists",
                    )

                # Generate cloud_config (no workspaces initially)
                cloud_config = self.generate_cloud_config(cfn_data.cfn_id, [])

                # Create new CFN record with offline status
                new_cfn = CognitiveFabricNodeModel(
                    cfn_id=cfn_data.cfn_id,
                    cfn_name=cfn_data.cfn_name,
                    cfn_config=cfn_data.cfn_config,
                    cloud_config=cloud_config,
                    status=CognitiveFabricNodeStatus.OFFLINE.value,
                    enabled=True,
                    last_seen=datetime.now(timezone.utc),
                    created_by=user_id,
                )

                session.add(new_cfn)
                session.flush()

                session.commit()
                session.refresh(new_cfn)

                response = CognitiveFabricNodeRegisterResponse(
                    cfn_id=new_cfn.cfn_id,
                    cfn_name=new_cfn.cfn_name,
                    status=CognitiveFabricNodeStatus(new_cfn.status),
                    cloud_config=new_cfn.cloud_config,
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
                elif "cognitive_fabric_node_pkey" in error_str:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with id '{cfn_data.cfn_id}' is already registered",
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
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Re-enable a disabled/de-registered CFN node (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (disabled/deleted)
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

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
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
        cfn.last_seen = datetime.now(timezone.utc)
        cfn.enabled = True
        cfn.deleted_at = None
        cfn.updated_at = datetime.now(timezone.utc)
        cfn.updated_by = user_id

        # Regenerate cloud_config with existing workspace associations
        workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
        cfn.cloud_config = self.generate_cloud_config(cfn.cfn_id, workspace_ids)

        session.commit()
        session.refresh(cfn)

        response = CognitiveFabricNodeRegisterResponse(
            cfn_id=cfn.cfn_id,
            cfn_name=cfn.cfn_name,
            status=CognitiveFabricNodeStatus(cfn.status),
            cloud_config=cfn.cloud_config,
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

    def _reuse_deleted_cfn(
        self,
        session,
        cfn: CognitiveFabricNodeModel,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Reuse a deleted CFN ID by updating the existing deleted record (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (deleted, deleted_at is set)
            cfn_data: CFN registration data
            user_id: User performing registration

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

        Raises:
            HTTPException: 409 if name conflict
        """
        # Update the deleted CFN to create a "new" CFN with the same ID
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
        cfn.last_seen = datetime.now(timezone.utc)
        cfn.enabled = True
        cfn.deleted_at = None
        cfn.updated_at = datetime.now(timezone.utc)
        cfn.updated_by = user_id
        cfn.created_at = datetime.now(timezone.utc)
        cfn.created_by = user_id

        # No workspace associations initially (done during workspace creation)
        cfn.cloud_config = self.generate_cloud_config(cfn.cfn_id, [])

        session.commit()
        session.refresh(cfn)

        response = CognitiveFabricNodeRegisterResponse(
            cfn_id=cfn.cfn_id,
            cfn_name=cfn.cfn_name,
            status=CognitiveFabricNodeStatus(cfn.status),
            cloud_config=cfn.cloud_config,
        )

        # Audit logging
        audit_service.create_audit(
            AuditRequest(
                resource_type=ResourceType.COGNITIVE_FABRIC_NODE,
                audit_type=AuditEventType.RESOURCE_CREATED,
                audit_resource_id=cfn.cfn_id,
                created_by=user_id,
                audit_information=cfn_data.model_dump(),
                audit_extra_information="CFN ID reused after deletion (new CFN created with same ID)",
                created_at=cfn.created_at,
            )
        )

        return response

    def _refresh_cfn(
        self,
        session,
        cfn: CognitiveFabricNodeModel,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Refresh an active CFN node during reboot/reconnection (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (active)
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

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

        # Update CFN config and refresh (keep existing workspace associations)
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
        cfn.last_seen = datetime.now(timezone.utc)
        cfn.updated_at = datetime.now(timezone.utc)
        cfn.updated_by = user_id

        workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
        cfn.cloud_config = self.generate_cloud_config(cfn.cfn_id, workspace_ids)

        session.commit()
        session.refresh(cfn)

        response = CognitiveFabricNodeRegisterResponse(
            cfn_id=cfn.cfn_id,
            cfn_name=cfn.cfn_name,
            status=CognitiveFabricNodeStatus(cfn.status),
            cloud_config=cfn.cloud_config,
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
    ) -> CognitiveFabricNodeDetail:
        """
        Update Cognitive Fabric Node

        Args:
            cfn_id: CFN identifier (immutable)
            cfn_data: Update data
            user_id: User performing update

        Returns:
            CognitiveFabricNodeDetail with updated information

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
                if cfn_data.cfn_config is not None:
                    cfn.cfn_config = cfn_data.cfn_config

                # Regenerate cloud_config
                workspace_ids = self._get_workspace_ids(session, cfn_id)
                cfn.cloud_config = self.generate_cloud_config(cfn_id, workspace_ids)

                # Update metadata
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                session.commit()
                session.refresh(cfn)

                response = CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    cfn_config=cfn.cfn_config,
                    cloud_config=cfn.cloud_config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
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

    def disable(self, cfn_id: str, user_id: str) -> CognitiveFabricNodeDetail:
        """
        Disable Cognitive Fabric Node (soft disable)

        Disabling a CFN stops heartbeats and prepares it for deletion.
        The CFN ID cannot be reused while in disabled state.
        A disabled CFN can be re-enabled via the enable endpoint.

        Args:
            cfn_id: CFN identifier
            user_id: User performing disable operation

        Returns:
            CognitiveFabricNodeDetail with updated information

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

                workspace_ids = self._get_workspace_ids(session, cfn_id)

                session.commit()
                session.refresh(cfn)

                response = CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    cfn_config=cfn.cfn_config,
                    cloud_config=cfn.cloud_config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
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

    def enable(self, cfn_id: str, user_id: str) -> CognitiveFabricNodeDetail:
        """
        Manually re-enable a disabled/de-registered CFN node

        This is a manual admin operation to re-enable a disabled CFN.
        After enabling, the CFN can call /register to reconnect.

        Args:
            cfn_id: CFN identifier
            user_id: User performing the enable operation

        Returns:
            CognitiveFabricNodeDetail with updated information

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

                workspace_ids = self._get_workspace_ids(session, cfn_id)

                session.commit()
                session.refresh(cfn)

                response = CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    cfn_config=cfn.cfn_config,
                    cloud_config=cfn.cloud_config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
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
            CognitiveFabricNodeHeartbeatResponse with status and last_seen

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
                    workspace_ids = self._get_workspace_ids(session, cfn.cfn_id)
                    node_list.append(
                        CognitiveFabricNodeListItem(
                            cfn_id=cfn.cfn_id,
                            workspace_ids=workspace_ids,
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

    def get(self, cfn_id: str) -> CognitiveFabricNodeDetail:
        """
        Get detailed Cognitive Fabric Node information

        Args:
            cfn_id: CFN identifier

        Returns:
            CognitiveFabricNodeDetail with full information

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

                workspace_ids = self._get_workspace_ids(session, cfn_id)

                return CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_ids=workspace_ids,
                    cfn_name=cfn.cfn_name,
                    cfn_config=cfn.cfn_config,
                    cloud_config=cfn.cloud_config,
                    status=CognitiveFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
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

    def generate_cloud_config(self, cfn_id: str, workspace_ids: List[str] = None) -> dict:
        """
        Generate cloud configuration for CFN

        Aggregates config from all associated workspaces.

        Args:
            cfn_id: CFN identifier
            workspace_ids: List of workspace IDs (if None, fetches from join table)

        Returns:
            Dictionary with cloud configuration
        """
        if workspace_ids is None:
            db = RelationalDB()
            session = db.get_session()
            try:
                workspace_ids = self._get_workspace_ids(session, cfn_id)
            finally:
                session.close()

        # Generate timestamp-based config_id
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        config_id = f"cfg-{timestamp}-{cfn_id[:8]}"

        # Get workspace details
        workspaces_info = []
        for ws_id in workspace_ids:
            ws = workspace_service.get(ws_id)
            if ws:
                workspaces_info.append(
                    {
                        "workspace_id": ws_id,
                        "workspace_name": ws.name if ws else "Unknown Workspace",
                    }
                )

        # Get CFN details
        db = RelationalDB()
        session = db.get_session()
        try:
            cfn = session.query(CognitiveFabricNodeModel).filter(CognitiveFabricNodeModel.cfn_id == cfn_id).first()

            cfn_name = cfn.cfn_name if cfn else "unknown"
            created_by = cfn.created_by if cfn else "system"
            created_at = (
                cfn.created_at.isoformat() if cfn and cfn.created_at else datetime.now(timezone.utc).isoformat()
            )
            updated_by = cfn.updated_by if cfn else created_by
            updated_at = (
                cfn.updated_at.isoformat() if cfn and cfn.updated_at else datetime.now(timezone.utc).isoformat()
            )
        finally:
            session.close()

        workspaces_payload = []
        for ws_id in workspace_ids:
            ws = workspace_service.get(ws_id)
            workspace_obj = {
                "workspace_id": ws_id,
                "workspace_name": ws.name if ws else "Unknown Workspace",
                "multi_agent_systems": [],
                "cognitive_engines": [],
                "cognitive_agents": [],
            }

            # Get Multi-Agentic Systems for this workspace
            try:
                mas_systems = multi_agentic_system_service.list_dummy(ws_id).systems
                workspace_obj["multi_agent_systems"] = [system.model_dump(mode="json") for system in mas_systems]
            except Exception:
                pass

            # Get Cognitive Engines for this workspace
            try:
                engines = cognitive_engine_service.list_dummy(ws_id).engines
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

            # Get Cognitive Agents for this workspace (global/built-in defaults)
            try:
                from server.database.relational_db.models.cognitive_agent import CognitiveAgent as CognitiveAgentModel

                db_agents = RelationalDB()
                session_agents = db_agents.get_session()
                try:
                    agents = (
                        session_agents.query(CognitiveAgentModel)
                        .filter(CognitiveAgentModel.enabled == True)  # noqa: E712
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

            workspaces_payload.append(workspace_obj)

        # Fetch Memory Providers (global, not workspace-scoped)
        try:
            providers = memory_provider_service.list_dummy().providers
            providers_payload = [
                {
                    "memory_provider_id": provider.memory_provider_id,
                    "name": provider.memory_provider_name,
                    "type": provider.provider_type,
                    "provider": provider.provider,
                    "enabled": provider.enabled,
                    "config": provider.config or {},
                }
                for provider in providers
            ]
        except Exception:
            providers_payload = []

        # Convert CFN model to dict for JSON serialization
        cfn_data = None
        if cfn:
            cfn_data = {
                "cfn_id": cfn.cfn_id,
                "cfn_name": cfn.cfn_name,
                "cfn_config": cfn.cfn_config,
                "status": cfn.status,
                "enabled": cfn.enabled,
                "created_by": cfn.created_by,
                "created_at": cfn.created_at.isoformat() if cfn.created_at else None,
                "updated_by": cfn.updated_by,
                "updated_at": cfn.updated_at.isoformat() if cfn.updated_at else None,
            }

        return {
            "version": "1.0",
            "config_id": config_id,
            "metadata": {
                "cfn_id": cfn_id,
                "cfn_name": cfn_name,
                "created_by": created_by,
                "created_at": created_at,
                "updated_by": updated_by,
                "updated_at": updated_at,
            },
            "workspaces": workspaces_payload,
            "memory_providers": providers_payload,
            "cognitive_fabric_node": cfn_data,
        }

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
