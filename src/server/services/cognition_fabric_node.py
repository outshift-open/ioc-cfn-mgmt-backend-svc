# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Fabric Node service - Business logic for Cognition Fabric Node operations"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognition_fabric_node import (
    CognitionFabricNode as CognitionFabricNodeModel,
)
from server.database.relational_db.models.workspace import Workspace as WorkspaceModel
from server.schemas.cognition_fabric_node import (
    CognitionFabricNodeHeartbeatResponse,
    CognitionFabricNodeList,
    CognitionFabricNodeListItem,
    CognitionFabricNodeRegisterRequest,
    CognitionFabricNodeResponse,
    CognitionFabricNodeStatus,
    CognitionFabricNodeUpdateRequest,
)
from server.services.cognition_engine import cognition_engine_service
from server.services.memory_provider import memory_provider_service
from server.services.multi_agentic_system import multi_agentic_system_service
from server.services.workspace import workspace_service
from server.utils import generate_uuid
from server.utils.encryption import process_config_for_cfn

# Set up module-level logger
logger = logging.getLogger(__name__)


class CognitionFabricNodeService:
    """Service layer for Cognition Fabric Node business logic"""

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
        Update config_version and regenerate config for all CFNs serving this workspace.

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
                    session.query(CognitionFabricNodeModel)
                    .filter(CognitionFabricNodeModel.id == workspace.cfn_id)
                    .first()
                )

                if cfn:
                    cfn.config_version = (cfn.config_version or 0) + 1

                    # Regenerate config
                    workspace_ids = self._get_workspace_ids(session, cfn.id)
                    cfn.config = self.generate_config(cfn.id, workspace_ids, cfn.cfn_config, cfn.config_version)

                    session.commit()

            finally:
                session.close()

        except Exception:
            # Silently fail to avoid breaking the calling operation
            pass

    def update_config_for_all_cfns(self) -> None:
        """
        Update config_version and regenerate config for all CFNs.

        Called when global resources change (cognitive agents, memory providers, etc.)
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Get all non-deleted CFNs
                cfns = (
                    session.query(CognitionFabricNodeModel).filter(CognitionFabricNodeModel.deleted_at.is_(None)).all()
                )

                for cfn in cfns:
                    cfn.config_version = (cfn.config_version or 0) + 1

                    # Regenerate config
                    workspace_ids = self._get_workspace_ids(session, cfn.id)
                    cfn.config = self.generate_config(cfn.id, workspace_ids, cfn.cfn_config, cfn.config_version)

                session.commit()

            finally:
                session.close()

        except Exception:
            # Silently fail to avoid breaking the calling operation
            pass

    def create(self, cfn_data: CognitionFabricNodeRegisterRequest, user_id: str) -> CognitionFabricNodeResponse:
        """
        Create a new Cognition Fabric Node or refresh an active one

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
            CognitionFabricNodeResponse with config

        Raises:
            HTTPException: 409 if name conflict, 403 if disabled
        """

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if cfn_name exists (only among non-deleted CFNs)
                existing_cfn = (
                    session.query(CognitionFabricNodeModel)
                    .filter(
                        CognitionFabricNodeModel.name == cfn_data.name,
                        CognitionFabricNodeModel.deleted_at.is_(None),
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
                cfn_id = generate_uuid()

                # Create new CFN record with offline status
                now = datetime.now(timezone.utc)

                # Generate config (no workspaces initially)
                initial_version = 1
                config = self.generate_config(cfn_id, [], cfn_data.cfn_config, initial_version)

                new_cfn = CognitionFabricNodeModel(
                    id=cfn_id,
                    name=cfn_data.name,
                    cfn_config=cfn_data.cfn_config,
                    config=config,
                    status=CognitionFabricNodeStatus.OFFLINE.value,
                    enabled=True,
                    last_seen=now,
                    config_version=initial_version,
                    ip_address=cfn_data.ip_address,
                    port=str(cfn_data.port) if cfn_data.port else None,
                    created_by=user_id,
                )

                session.add(new_cfn)
                session.flush()

                session.commit()
                session.refresh(new_cfn)

                # If this is the default-cfn and Default Workspace exists without a CFN, associate them
                workspace_ids_list = []
                if cfn_data.name == os.getenv("CFN_NAME", "My Cognition Fabric Node"):
                    default_workspace = (
                        session.query(WorkspaceModel)
                        .filter(
                            WorkspaceModel.name == workspace_service.DEFAULT_WORKSPACE_NAME,
                            WorkspaceModel.cfn_id.is_(None),
                            WorkspaceModel.deleted_at.is_(None),
                        )
                        .first()
                    )

                    if not default_workspace:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=(
                                "Default workspace not found or already has a CFN assigned. "
                                "Please create a workspace with name 'default' without a CFN to enable automatic"
                                " association."
                            ),
                        )

                    # Associate workspace with default CFN
                    default_workspace.cfn_id = cfn_id
                    default_workspace.updated_at = datetime.now(timezone.utc)

                    # Regenerate CFN config with the workspace
                    workspace_ids_list = [default_workspace.id]
                    new_cfn.config_version = (new_cfn.config_version or 0) + 1
                    new_cfn.config = self.generate_config(cfn_id, workspace_ids_list, cfn_data.cfn_config, new_cfn.config_version)

                    session.commit()
                    session.refresh(new_cfn)
                    logger.info(f"Automatically associated new CFN '{cfn_data.name}' with default workspace")

                # Build response with workspace associations (if any)
                response = CognitionFabricNodeResponse(
                    id=new_cfn.id,
                    workspace_ids=workspace_ids_list,
                    name=new_cfn.name,
                    config=new_cfn.config,
                    status=CognitionFabricNodeStatus(new_cfn.status),
                    last_seen=new_cfn.last_seen,
                    enabled=new_cfn.enabled,
                    ip_address=new_cfn.ip_address,
                    port=int(new_cfn.port) if new_cfn.port else None,
                    created_at=new_cfn.created_at,
                    updated_at=new_cfn.updated_at,
                    created_by=new_cfn.created_by,
                    updated_by=new_cfn.updated_by,
                )

                return response

            except IntegrityError as e:
                session.rollback()
                error_str = str(e)
                if "idx_cfn_name_unique" in error_str:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.name}' already exists",
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
        cfn: CognitionFabricNodeModel,
        cfn_data: CognitionFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitionFabricNodeResponse:
        """
        Re-enable a disabled/de-registered CFN node (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (disabled/deleted)
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitionFabricNodeResponse with config

        Raises:
            HTTPException: 409 if name conflict
        """
        # Check if cfn_name conflicts with another active CFN (globally unique)
        if cfn_data.name != cfn.name:
            existing_name = (
                session.query(CognitionFabricNodeModel)
                .filter(
                    CognitionFabricNodeModel.name == cfn_data.name,
                    CognitionFabricNodeModel.id != cfn.id,
                    CognitionFabricNodeModel.deleted_at.is_(None),
                )
                .first()
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CFN with name '{cfn_data.name}' already exists",
                )

        # Re-activate the CFN with offline status
        now = datetime.now(timezone.utc)
        cfn.name = cfn_data.name
        cfn.cfn_config = cfn_data.cfn_config
        cfn.status = CognitionFabricNodeStatus.OFFLINE.value
        cfn.last_seen = now
        cfn.enabled = True
        cfn.deleted_at = None
        cfn.updated_at = now
        cfn.updated_by = user_id

        # Regenerate config with existing workspace associations
        workspace_ids = self._get_workspace_ids(session, cfn.id)
        cfn.config_version = (cfn.config_version or 0) + 1
        cfn.config = self.generate_config(cfn.id, workspace_ids, cfn.cfn_config, cfn.config_version)

        session.commit()
        session.refresh(cfn)

        response = CognitionFabricNodeResponse(
            id=cfn.id,
            workspace_ids=workspace_ids,
            name=cfn.name,
            config=cfn.config,
            status=CognitionFabricNodeStatus(cfn.status),
            last_seen=cfn.last_seen,
            enabled=cfn.enabled,
            ip_address=cfn.ip_address,
            port=int(cfn.port) if cfn.port else None,
            created_at=cfn.created_at,
            updated_at=cfn.updated_at,
            created_by=cfn.created_by,
            updated_by=cfn.updated_by,
        )

        return response

    def _refresh_cfn(
        self,
        session,
        cfn: CognitionFabricNodeModel,
        cfn_data: CognitionFabricNodeRegisterRequest,
        user_id: str,
    ) -> CognitionFabricNodeResponse:
        """
        Refresh an active CFN node during reboot/reconnection (internal method)

        Args:
            session: Database session
            cfn: Existing CFN model instance (active, found by name)
            cfn_data: CFN registration data
            user_id: User performing re-registration

        Returns:
            CognitionFabricNodeResponse with config
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

        workspace_ids = self._get_workspace_ids(session, cfn.id)
        cfn.config_version = (cfn.config_version or 0) + 1
        cfn.config = self.generate_config(cfn.id, workspace_ids, cfn.cfn_config, cfn.config_version)

        session.commit()
        session.refresh(cfn)

        response = CognitionFabricNodeResponse(
            id=cfn.id,
            workspace_ids=workspace_ids,
            name=cfn.name,
            config=cfn.config,
            status=CognitionFabricNodeStatus(cfn.status),
            last_seen=cfn.last_seen,
            enabled=cfn.enabled,
            ip_address=cfn.ip_address,
            port=int(cfn.port) if cfn.port else None,
            created_at=cfn.created_at,
            updated_at=cfn.updated_at,
            created_by=cfn.created_by,
            updated_by=cfn.updated_by,
        )

        return response

    def update(
        self, cfn_id: str, cfn_data: CognitionFabricNodeUpdateRequest, user_id: str
    ) -> CognitionFabricNodeResponse:
        """
        Update Cognition Fabric Node

        Args:
            cfn_id: CFN identifier (immutable)
            cfn_data: Update data
            user_id: User performing update

        Returns:
            CognitionFabricNodeResponse with updated information

        Raises:
            HTTPException: 404 if not found, 409 if name conflict
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN
                cfn = (
                    session.query(CognitionFabricNodeModel)
                    .filter(
                        CognitionFabricNodeModel.id == cfn_id,
                        CognitionFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Update cfn_name if provided (check global uniqueness)
                if cfn_data.name is not None:
                    existing_name = (
                        session.query(CognitionFabricNodeModel)
                        .filter(
                            CognitionFabricNodeModel.name == cfn_data.name,
                            CognitionFabricNodeModel.id != cfn_id,
                            CognitionFabricNodeModel.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if existing_name:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"CFN with name '{cfn_data.name}' already exists",
                        )
                    cfn.name = cfn_data.name

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

                # Bump config_version if config changed
                if config_changed or cfn_data.name is not None:
                    cfn.config_version = (cfn.config_version or 0) + 1

                # Generate config with version
                cfn.config = self.generate_config(cfn_id, workspace_ids, cfn.cfn_config, cfn.config_version)

                session.commit()
                session.refresh(cfn)

                response = CognitionFabricNodeResponse(
                    id=cfn.id,
                    workspace_ids=workspace_ids,
                    name=cfn.name,
                    config=cfn.config,
                    status=CognitionFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
                )

                return response

            except IntegrityError as e:
                session.rollback()
                if "idx_cfn_name_unique" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"CFN with name '{cfn_data.name}' already exists",
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

    def disable(self, cfn_id: str, user_id: str) -> CognitionFabricNodeResponse:
        """
        Disable Cognition Fabric Node (soft disable)

        Disabling a CFN stops heartbeats and prepares it for deletion.
        The CFN ID cannot be reused while in disabled state.
        A disabled CFN can be re-enabled via the enable endpoint.

        Args:
            cfn_id: CFN identifier
            user_id: User performing disable operation

        Returns:
            CognitionFabricNodeResponse with updated information

        Raises:
            HTTPException: 404 if not found, 400 if already disabled
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN (only active ones)
                cfn = (
                    session.query(CognitionFabricNodeModel)
                    .filter(
                        CognitionFabricNodeModel.id == cfn_id,
                        CognitionFabricNodeModel.deleted_at.is_(None),
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

                response = CognitionFabricNodeResponse(
                    id=cfn.id,
                    workspace_ids=workspace_ids,
                    name=cfn.name,
                    config=cfn.config,
                    status=CognitionFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
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
        Delete Cognition Fabric Node (hard delete)

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
                    session.query(CognitionFabricNodeModel)
                    .filter(
                        CognitionFabricNodeModel.id == cfn_id,
                        CognitionFabricNodeModel.deleted_at.is_(None),
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

    def enable(self, cfn_id: str, user_id: str) -> CognitionFabricNodeResponse:
        """
        Manually re-enable a disabled/de-registered CFN node

        This is a manual admin operation to re-enable a disabled CFN.
        After enabling, the CFN can call /register to reconnect.

        Args:
            cfn_id: CFN identifier
            user_id: User performing the enable operation

        Returns:
            CognitionFabricNodeResponse with updated information

        Raises:
            HTTPException: 404 if not found, 400 if already enabled
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN (including disabled ones)
                cfn = session.query(CognitionFabricNodeModel).filter(CognitionFabricNodeModel.id == cfn_id).first()

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
                cfn.status = CognitionFabricNodeStatus.OFFLINE.value
                cfn.updated_at = datetime.now(timezone.utc)
                cfn.updated_by = user_id

                session.commit()
                session.refresh(cfn)

                # Get associated workspace IDs
                workspace_ids = self._get_workspace_ids(session, cfn_id)

                response = CognitionFabricNodeResponse(
                    id=cfn.id,
                    workspace_ids=workspace_ids,
                    name=cfn.name,
                    config=cfn.config,
                    status=CognitionFabricNodeStatus(cfn.status),
                    last_seen=cfn.last_seen,
                    enabled=cfn.enabled,
                    ip_address=cfn.ip_address,
                    port=int(cfn.port) if cfn.port else None,
                    created_at=cfn.created_at,
                    updated_at=cfn.updated_at,
                    created_by=cfn.created_by,
                    updated_by=cfn.updated_by,
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

    def heartbeat(self, cfn_id: str) -> CognitionFabricNodeHeartbeatResponse:
        """
        Update CFN heartbeat

        Args:
            cfn_id: CFN identifier

        Returns:
            CognitionFabricNodeHeartbeatResponse with status, last_seen, and config_version

        Raises:
            HTTPException: 404 if not found, 403 if blocked
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the CFN
                cfn = session.query(CognitionFabricNodeModel).filter(CognitionFabricNodeModel.id == cfn_id).first()

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
                if cfn.status == CognitionFabricNodeStatus.OFFLINE.value:
                    cfn.status = CognitionFabricNodeStatus.ONLINE.value

                session.commit()
                session.refresh(cfn)

                # Ensure timestamps have timezone info for consistent ISO format serialization
                last_seen = (
                    cfn.last_seen.replace(tzinfo=timezone.utc)
                    if cfn.last_seen and cfn.last_seen.tzinfo is None
                    else cfn.last_seen
                )

                return CognitionFabricNodeHeartbeatResponse(
                    status=CognitionFabricNodeStatus(cfn.status),
                    last_seen=last_seen,
                    config_version=cfn.config_version or 0,
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

    def list(self, workspace_id: Optional[str] = None, status_filter: Optional[str] = None) -> CognitionFabricNodeList:
        """
        List all Cognition Fabric Nodes, optionally filtered by workspace

        Returns all CFNs (enabled and disabled). Deleted CFNs are never included.

        Args:
            workspace_id: Optional workspace filter (filters to CFN assigned to that workspace)
            status_filter: Optional status filter (online, offline, blocked)

        Returns:
            CognitionFabricNodeList with nodes and total count

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
                query = session.query(CognitionFabricNodeModel).filter(
                    CognitionFabricNodeModel.deleted_at.is_(None),
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
                        query = query.filter(CognitionFabricNodeModel.id == workspace.cfn_id)
                    else:
                        # Workspace has no CFN assigned, return empty list
                        return CognitionFabricNodeList(nodes=[], total=0)

                # Apply status filter if provided
                if status_filter:
                    query = query.filter(CognitionFabricNodeModel.status == status_filter)

                cfns = query.all()

                node_list = []
                for cfn in cfns:
                    node_list.append(
                        CognitionFabricNodeListItem(
                            id=cfn.id,
                            name=cfn.name,
                            status=CognitionFabricNodeStatus(cfn.status),
                            last_seen=cfn.last_seen,
                            enabled=cfn.enabled,
                            created_at=cfn.created_at,
                        )
                    )

                return CognitionFabricNodeList(nodes=node_list, total=len(node_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list CFN nodes: {str(e)}",
            )

    def get(self, cfn_id: str) -> CognitionFabricNodeResponse:
        """
        Get detailed Cognition Fabric Node information

        Args:
            cfn_id: CFN identifier

        Returns:
            CognitionFabricNodeResponse with full information

        Raises:
            HTTPException: 404 if not found
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                cfn = (
                    session.query(CognitionFabricNodeModel)
                    .filter(
                        CognitionFabricNodeModel.id == cfn_id,
                        CognitionFabricNodeModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="CFN node not found",
                    )

                # Get associated workspace IDs
                workspace_ids = self._get_workspace_ids(session, cfn.id)

                return CognitionFabricNodeResponse(
                    id=cfn.id,
                    workspace_ids=workspace_ids,
                    name=cfn.name,
                    config=cfn.config,
                    status=CognitionFabricNodeStatus(cfn.status),
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
        self, cfn_id: str, workspace_ids: List[str] = None, cfn_config: dict = None, config_version: int = 0
    ) -> dict:
        """
        Generate configuration for CFN

        Aggregates config from all associated workspaces.

        Args:
            cfn_id: CFN identifier
            workspace_ids: List of workspace IDs (if None, fetches from join table)
            cfn_config: CFN-specific configuration to include in the config
            config_version: Monotonic version counter for change detection

        Returns:
            Dictionary with configuration including cfn_config and config_version
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
                    "cognition_engines": [],
                    "policies": [],
                }

                # Get Multi-Agentic Systems for this workspace
                try:
                    mas_systems = multi_agentic_system_service.list(ws_id).systems
                    mas_systems_data = []
                    for system in mas_systems:
                        system_data = system.model_dump(mode="json", exclude_none=False)

                        # Process memory provider configs for CFN (decrypt credentials)
                        if system_data.get("shared_memory") and system_data["shared_memory"].get("config"):
                            system_data["shared_memory"]["config"] = process_config_for_cfn(
                                system_data["shared_memory"]["config"]
                            )

                        # Process agent memory provider configs
                        if system_data.get("agents"):
                            for agent in system_data["agents"]:
                                if agent.get("agentic_memory") and agent["agentic_memory"].get("config"):
                                    agent["agentic_memory"]["config"] = process_config_for_cfn(
                                        agent["agentic_memory"]["config"]
                                    )

                        mas_systems_data.append(system_data)

                    workspace_obj["multi_agentic_systems"] = mas_systems_data
                except Exception as e:
                    logger.error(f"Error processing MAS for CFN: {e}", exc_info=True)

                # Get Cognition Engines for this workspace
                try:
                    engines = cognition_engine_service.list(ws_id).engines
                    workspace_obj["cognition_engines"] = [
                        {
                            "id": engine.id,
                            "name": engine.name,
                            "config": engine.config or {},
                            "enabled": engine.enabled,
                        }
                        for engine in engines
                    ]
                except Exception:
                    pass

                workspaces_payload.append(workspace_obj)

            # Fetch Memory Providers (global, not workspace-scoped)
            try:
                providers = memory_provider_service.list_for_cfn()
                providers_payload = [
                    {
                        "id": provider["id"],
                        "name": provider["name"],
                        "description": provider["description"],
                        "enabled": provider["enabled"],
                        "config": process_config_for_cfn(provider["config"] or {}),
                    }
                    for provider in providers
                ]
            except Exception:
                providers_payload = []

            return {
                "config_version": config_version,
                "cfn_config": cfn_config or {},
                "workspaces": workspaces_payload,
                "memory_providers": providers_payload,
            }

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
                    session.query(CognitionFabricNodeModel)
                    .filter(
                        and_(
                            CognitionFabricNodeModel.status == CognitionFabricNodeStatus.ONLINE.value,
                            CognitionFabricNodeModel.last_seen < threshold_time,
                            CognitionFabricNodeModel.deleted_at.is_(None),
                        )
                    )
                    .all()
                )

                count = 0
                for cfn in stale_nodes:
                    cfn.status = CognitionFabricNodeStatus.OFFLINE.value
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
cognition_fabric_node_service = CognitionFabricNodeService()
