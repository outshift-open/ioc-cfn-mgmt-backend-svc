"""Cognitive Fabric Node service - Business logic for Cognitive Fabric Node operations"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognitive_fabric_node import (
    CognitiveFabricNode as CognitiveFabricNodeModel,
)
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
from server.services.workspace import workspace_service


class CognitiveFabricNodeService:
    """Service layer for Cognitive Fabric Node business logic"""

    def create(
        self, workspace_id: str, cfn_data: CognitiveFabricNodeRegisterRequest, user_id: str
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Create a new Cognitive Fabric Node or refresh an active one

        CFN nodes are like IoT devices - they always call this endpoint.
        The service handles 4 scenarios:
        1. New CFN: Create new CFN entry
        2. Deleted CFN (ID reuse): Update deleted record to create new CFN with same ID
        3. Active CFN reconnection: Refresh config (allows reboot/reconciliation)
        4. Disabled CFN: Return 403 Forbidden (requires manual re-enable)

        Args:
            workspace_id: Workspace identifier
            cfn_data: CFN registration data
            user_id: User creating the CFN

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

        Raises:
            HTTPException: 404 if workspace not found, 403 if disabled
        """
        # Validate workspace exists
        if not workspace_service.exists(workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

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
                    # UPDATE the existing deleted record instead of creating new
                    if existing_cfn.deleted_at is not None:
                        # ID is available for reuse
                        # Check if new name conflicts with another ACTIVE CFN (not the deleted one)
                        conflicting_name = (
                            session.query(CognitiveFabricNodeModel)
                            .filter(
                                CognitiveFabricNodeModel.workspace_id == workspace_id,
                                CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                                CognitiveFabricNodeModel.deleted_at.is_(None),
                                CognitiveFabricNodeModel.cfn_id != cfn_data.cfn_id,  # Exclude the deleted CFN itself
                            )
                            .first()
                        )
                        if conflicting_name:
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
                            )

                        # Reuse the deleted CFN ID by updating the existing record
                        return self._reuse_deleted_cfn(session, existing_cfn, workspace_id, cfn_data, user_id)

                    # Scenario 2a: CFN is disabled (but not deleted) - ID is LOCKED, cannot reuse
                    elif not existing_cfn.enabled:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="CFN node has been disabled. Contact workspace admin to re-enable it first.",
                        )

                    # Scenario 2b: CFN is active - Allow reboot/reconnection (refresh config)
                    else:
                        # Check workspace matches
                        if existing_cfn.workspace_id != workspace_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"CFN '{cfn_data.cfn_id}' is active in a different workspace",
                            )

                        # Refresh existing CFN (reboot/reconnection)
                        return self._refresh_cfn(session, existing_cfn, workspace_id, cfn_data, user_id)

                # Scenario 3: New CFN (no existing_cfn) - Create new entry
                # Check if cfn_name already exists in this workspace
                if not existing_cfn or existing_cfn.deleted_at is not None:
                    # Only check name conflicts if this is truly a new CFN or reusing a deleted ID
                    existing_name = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(
                            CognitiveFabricNodeModel.workspace_id == workspace_id,
                            CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                            CognitiveFabricNodeModel.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if existing_name:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
                        )

                # Generate cloud_config
                cloud_config = self.generate_cloud_config(workspace_id, cfn_data.cfn_id)

                # Create new CFN record with offline status
                # CFN must send heartbeat to become online
                new_cfn = CognitiveFabricNodeModel(
                    cfn_id=cfn_data.cfn_id,
                    workspace_id=workspace_id,
                    cfn_name=cfn_data.cfn_name,
                    cfn_config=cfn_data.cfn_config,
                    cloud_config=cloud_config,
                    status=CognitiveFabricNodeStatus.OFFLINE.value,
                    enabled=True,
                    last_seen=datetime.now(timezone.utc),
                    created_by=user_id,
                )

                session.add(new_cfn)
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
                if "idx_cfn_workspace_name_unique" in error_str:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
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
        workspace_id: str,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Re-enable a disabled/de-registered CFN node (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (disabled/deleted)
            workspace_id: Workspace identifier
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

        Raises:
            HTTPException: 409 if name conflict, 403 if workspace mismatch
        """
        # Check if workspace matches
        if cfn.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"CFN '{cfn_data.cfn_id}' was previously registered in a different workspace",
            )

        # Check if cfn_name conflicts with another active CFN in the workspace
        if cfn_data.cfn_name != cfn.cfn_name:
            existing_name = (
                session.query(CognitiveFabricNodeModel)
                .filter(
                    CognitiveFabricNodeModel.workspace_id == workspace_id,
                    CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                    CognitiveFabricNodeModel.cfn_id != cfn_data.cfn_id,
                    CognitiveFabricNodeModel.deleted_at.is_(None),
                )
                .first()
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
                )

        # Re-activate the CFN with offline status
        # CFN must send heartbeat to become online
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.cloud_config = self.generate_cloud_config(workspace_id, cfn_data.cfn_id)
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value
        cfn.last_seen = datetime.now(timezone.utc)
        cfn.enabled = True
        cfn.deleted_at = None
        cfn.updated_at = datetime.now(timezone.utc)
        cfn.updated_by = user_id

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
        workspace_id: str,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Reuse a deleted CFN ID by updating the existing deleted record (internal method)

        This allows CFN IDs to be reused after deregistration (hard delete).
        The existing deleted record is updated with new data, effectively creating
        a "new" CFN with the same ID.

        Args:
            session: Database session
            cfn: Existing CFN model instance (deleted, deleted_at is set)
            workspace_id: Workspace identifier
            cfn_data: CFN registration data
            user_id: User performing registration

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

        Raises:
            HTTPException: 409 if name conflict
        """
        # Update the deleted CFN to create a "new" CFN with the same ID
        cfn.workspace_id = workspace_id
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.cloud_config = self.generate_cloud_config(workspace_id, cfn_data.cfn_id)
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value  # Offline until heartbeat
        cfn.last_seen = datetime.now(timezone.utc)
        cfn.enabled = True  # Re-enable
        cfn.deleted_at = None  # Clear deletion marker
        cfn.updated_at = datetime.now(timezone.utc)
        cfn.updated_by = user_id
        cfn.created_at = datetime.now(timezone.utc)  # Reset creation time
        cfn.created_by = user_id

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
        workspace_id: str,
        cfn_data: CognitiveFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitiveFabricNodeRegisterResponse:
        """
        Refresh an active CFN node during reboot/reconnection (internal method)

        This allows CFN nodes to re-register with updated config after reboot.
        Status remains offline until heartbeat is sent.

        Args:
            session: Database session
            cfn: Existing CFN model instance (active)
            workspace_id: Workspace identifier
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitiveFabricNodeRegisterResponse with cloud_config

        Raises:
            HTTPException: 409 if name conflict
        """
        # Check if cfn_name conflicts with another active CFN in the workspace
        if cfn_data.cfn_name != cfn.cfn_name:
            existing_name = (
                session.query(CognitiveFabricNodeModel)
                .filter(
                    CognitiveFabricNodeModel.workspace_id == workspace_id,
                    CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                    CognitiveFabricNodeModel.cfn_id != cfn_data.cfn_id,
                    CognitiveFabricNodeModel.deleted_at.is_(None),
                )
                .first()
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
                )

        # Update CFN config and refresh
        cfn.cfn_name = cfn_data.cfn_name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.cloud_config = self.generate_cloud_config(workspace_id, cfn_data.cfn_id)
        cfn.status = CognitiveFabricNodeStatus.OFFLINE.value  # Offline until heartbeat
        cfn.last_seen = datetime.now(timezone.utc)
        cfn.updated_at = datetime.now(timezone.utc)
        cfn.updated_by = user_id

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
        self, workspace_id: str, cfn_id: str, cfn_data: CognitiveFabricNodeUpdateRequest, user_id: str
    ) -> CognitiveFabricNodeDetail:
        """
        Update Cognitive Fabric Node

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier (immutable)
            cfn_data: Update data
            user_id: User performing update

        Returns:
            CognitiveFabricNodeDetail with updated information

        Raises:
            HTTPException: 404 if not found, 403 if wrong workspace, 409 if name conflict
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

                # Validate CFN belongs to the workspace
                if cfn.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node does not belong to this workspace",
                    )

                # Update cfn_name if provided (check uniqueness)
                if cfn_data.cfn_name is not None:
                    existing_name = (
                        session.query(CognitiveFabricNodeModel)
                        .filter(
                            CognitiveFabricNodeModel.workspace_id == workspace_id,
                            CognitiveFabricNodeModel.cfn_name == cfn_data.cfn_name,
                            CognitiveFabricNodeModel.cfn_id != cfn_id,
                            CognitiveFabricNodeModel.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if existing_name:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
                        )
                    cfn.cfn_name = cfn_data.cfn_name

                # Update config if provided
                if cfn_data.cfn_config is not None:
                    cfn.cfn_config = cfn_data.cfn_config

                # Regenerate cloud_config
                cfn.cloud_config = self.generate_cloud_config(workspace_id, cfn_id)

                # Update metadata
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                session.commit()
                session.refresh(cfn)

                response = CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_id=cfn.workspace_id,
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
                if "idx_cfn_workspace_name_unique" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.cfn_name}' already exists in this workspace",
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

    def disable(self, workspace_id: str, cfn_id: str, user_id: str) -> CognitiveFabricNodeDetail:
        """
        Disable Cognitive Fabric Node (soft disable)

        Disabling a CFN stops heartbeats and prepares it for deletion.
        The CFN ID cannot be reused while in disabled state.
        A disabled CFN can be re-enabled via the enable endpoint.

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier
            user_id: User performing disable operation

        Returns:
            CognitiveFabricNodeDetail with updated information

        Raises:
            HTTPException: 404 if not found, 403 if wrong workspace, 400 if already disabled
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

                # Validate CFN belongs to the workspace
                if cfn.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node does not belong to this workspace",
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

                response = CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_id=cfn.workspace_id,
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

    def delete(self, workspace_id: str, cfn_id: str, user_id: str) -> None:
        """
        Delete Cognitive Fabric Node (hard delete)

        Deleting a CFN marks it as deleted in the database.
        The CFN ID can be reused to create a new CFN node after deletion.
        A CFN must be disabled before it can be deleted.

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier
            user_id: User performing deletion

        Raises:
            HTTPException: 404 if not found, 403 if wrong workspace, 400 if not disabled
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

                # Validate CFN belongs to the workspace
                if cfn.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node does not belong to this workspace",
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

    def enable(self, workspace_id: str, cfn_id: str, user_id: str) -> CognitiveFabricNodeDetail:
        """
        Manually re-enable a disabled/de-registered CFN node

        This is a manual admin operation to re-enable a disabled CFN.
        After enabling, the CFN can call /register to reconnect.

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier
            user_id: User performing the enable operation

        Returns:
            CognitiveFabricNodeDetail with updated information

        Raises:
            HTTPException: 404 if not found, 403 if wrong workspace, 400 if already enabled
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

                # Validate CFN belongs to the workspace
                if cfn.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node does not belong to this workspace",
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
                cfn.status = CognitiveFabricNodeStatus.OFFLINE.value  # Will become online after heartbeat
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                session.commit()
                session.refresh(cfn)

                response = CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_id=cfn.workspace_id,
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

    def heartbeat(self, workspace_id: str, cfn_id: str) -> CognitiveFabricNodeHeartbeatResponse:
        """
        Update CFN heartbeat

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier

        Returns:
            CognitiveFabricNodeHeartbeatResponse with status and last_seen

        Raises:
            HTTPException: 404 if not found, 403 if blocked or wrong workspace
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

                # Validate CFN belongs to the workspace
                if cfn.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node does not belong to this workspace",
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

    def list(self, workspace_id: str, status_filter: Optional[str] = None) -> CognitiveFabricNodeList:
        """
        List all Cognitive Fabric Nodes in workspace

        Returns all CFNs (enabled and disabled) in the workspace.
        Deleted CFNs are never included.

        Args:
            workspace_id: Workspace identifier
            status_filter: Optional status filter (online, offline, blocked)

        Returns:
            CognitiveFabricNodeList with nodes and total count

        Raises:
            HTTPException: 404 if workspace not found
        """
        # Validate workspace exists
        if not workspace_service.exists(workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Base query - exclude only deleted CFNs (include both enabled and disabled)
                query = session.query(CognitiveFabricNodeModel).filter(
                    and_(
                        CognitiveFabricNodeModel.workspace_id == workspace_id,
                        CognitiveFabricNodeModel.deleted_at.is_(None),
                    )
                )

                # Apply status filter if provided
                if status_filter:
                    query = query.filter(CognitiveFabricNodeModel.status == status_filter)

                cfns = query.all()

                node_list = [
                    CognitiveFabricNodeListItem(
                        cfn_id=cfn.cfn_id,
                        workspace_id=cfn.workspace_id,
                        cfn_name=cfn.cfn_name,
                        status=CognitiveFabricNodeStatus(cfn.status),
                        last_seen=cfn.last_seen,
                        enabled=cfn.enabled,
                        created_at=cfn.created_at,
                    )
                    for cfn in cfns
                ]

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

    def get(self, workspace_id: str, cfn_id: str) -> CognitiveFabricNodeDetail:
        """
        Get detailed Cognitive Fabric Node information

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier

        Returns:
            CognitiveFabricNodeDetail with full information

        Raises:
            HTTPException: 404 if not found, 403 if wrong workspace
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

                # Validate CFN belongs to the workspace
                if cfn.workspace_id != workspace_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CFN node does not belong to this workspace",
                    )

                return CognitiveFabricNodeDetail(
                    cfn_id=cfn.cfn_id,
                    workspace_id=cfn.workspace_id,
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

    def generate_cloud_config(self, workspace_id: str, cfn_id: str) -> dict:
        """
        Generate cloud configuration for CFN

        Args:
            workspace_id: Workspace identifier
            cfn_id: CFN identifier

        Returns:
            Dictionary with cloud configuration
        """
        return {
            "workspace_id": workspace_id,
            "log_level": "INFO",
            "features": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
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
