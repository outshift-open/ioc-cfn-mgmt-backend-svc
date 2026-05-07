# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine service - Business logic for Cognition Engine operations"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognition_engine import CognitionEngine as CognitionEngineModel
from server.schemas.cognition_engine import (
    CognitionEngineCreate,
    CognitionEngineDetail,
    CognitionEngineList,
    CognitionEngineListItem,
    CognitionEngineUpdate,
)
from server.services.workspace import workspace_service
from server.utils import generate_uuid


class CognitionEngineService:
    """Service layer for Cognition Engine business logic"""

    def create(self, workspace_id: str, engine_data: CognitionEngineCreate, user_id: str) -> CognitionEngineDetail:
        """
        Create a new Cognition Engine

        Args:
            workspace_id: Workspace identifier
            engine_data: Cognition engine creation data
            user_id: ID of the user creating the engine

        Returns:
            CognitionEngineDetail with the created engine

        Raises:
            HTTPException: If engine with same name already exists in workspace or creation fails
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
                # Check if engine with same name already exists in this workspace
                existing_engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.workspace_id == workspace_id,
                        CognitionEngineModel.name == engine_data.name,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing_engine:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Cognition engine with name '{engine_data.name}' "
                            f"already exists in this workspace"
                        ),
                    )

                # Generate unique ID for the engine
                cognition_engine_id = generate_uuid()

                # Create new engine
                new_engine = CognitionEngineModel(
                    id=cognition_engine_id,
                    workspace_id=workspace_id,
                    name=engine_data.name,
                    config=engine_data.config,
                    enabled=True,
                    created_by=user_id,
                )

                session.add(new_engine)
                session.commit()
                session.refresh(new_engine)

                # Update all CFN configs since engines are workspace-scoped
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_all_cfns()

                return CognitionEngineDetail(
                    id=new_engine.id,
                    workspace_id=new_engine.workspace_id,
                    name=new_engine.name,
                    config=new_engine.config,
                    enabled=new_engine.enabled,
                    created_at=new_engine.created_at,
                    updated_at=new_engine.updated_at,
                    created_by=new_engine.created_by,
                    updated_by=new_engine.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create cognition engine: {str(e)}",
            )

    def get(self, workspace_id: str, cognition_engine_id: str) -> CognitionEngineDetail:
        """
        Get a specific Cognition Engine by ID

        Args:
            workspace_id: Workspace identifier
            cognition_engine_id: ID of the cognition engine

        Returns:
            CognitionEngineDetail with the engine details

        Raises:
            HTTPException: If engine not found
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
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.workspace_id == workspace_id,
                        CognitionEngineModel.id == cognition_engine_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognition engine with ID '{cognition_engine_id}' not found in this workspace",
                    )

                return CognitionEngineDetail(
                    id=engine.id,
                    workspace_id=engine.workspace_id,
                    name=engine.name,
                    config=engine.config,
                    enabled=engine.enabled,
                    created_at=engine.created_at,
                    updated_at=engine.updated_at,
                    created_by=engine.created_by,
                    updated_by=engine.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get cognition engine: {str(e)}",
            )

    def list(self, workspace_id: str) -> CognitionEngineList:
        """
        List all Cognition Engines in workspace

        Args:
            workspace_id: Workspace identifier

        Returns:
            CognitionEngineList with engines and total count
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
                # Query all enabled engines in workspace
                engines = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.workspace_id == workspace_id,
                        CognitionEngineModel.deleted_at.is_(None),
                        CognitionEngineModel.enabled.is_(True),
                    )
                    .all()
                )

                engine_list = [
                    CognitionEngineListItem(
                        id=engine.id,
                        workspace_id=engine.workspace_id,
                        name=engine.name,
                        config=engine.config,
                        enabled=engine.enabled,
                        created_at=engine.created_at.isoformat() if engine.created_at else None,
                    )
                    for engine in engines
                ]

                return CognitionEngineList(engines=engine_list, total=len(engine_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list cognition engines: {str(e)}",
            )

    def update(
        self, workspace_id: str, cognition_engine_id: str, update_data: CognitionEngineUpdate, user_id: str
    ) -> CognitionEngineDetail:
        """
        Update a Cognition Engine

        Args:
            workspace_id: Workspace identifier
            cognition_engine_id: ID of the cognition engine to update
            update_data: Cognition engine update data
            user_id: ID of the user updating the engine

        Returns:
            CognitionEngineDetail with the updated engine

        Raises:
            HTTPException: If engine not found or update fails
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
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.workspace_id == workspace_id,
                        CognitionEngineModel.id == cognition_engine_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognition engine with ID '{cognition_engine_id}' not found in this workspace",
                    )

                # Update fields if provided
                if update_data.name is not None:
                    engine.name = update_data.name
                if update_data.config is not None:
                    engine.config = update_data.config
                if update_data.enabled is not None:
                    engine.enabled = update_data.enabled

                engine.updated_by = user_id
                engine.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(engine)

                # Update all CFN configs since engines are workspace-scoped
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_all_cfns()

                return CognitionEngineDetail(
                    id=engine.id,
                    workspace_id=engine.workspace_id,
                    name=engine.name,
                    config=engine.config,
                    enabled=engine.enabled,
                    created_at=engine.created_at,
                    updated_at=engine.updated_at,
                    created_by=engine.created_by,
                    updated_by=engine.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update cognition engine: {str(e)}",
            )

    def delete(self, workspace_id: str, cognition_engine_id: str, user_id: str) -> dict:
        """
        Soft delete a Cognition Engine

        Args:
            workspace_id: Workspace identifier
            cognition_engine_id: ID of the cognition engine to delete
            user_id: ID of the user deleting the engine

        Returns:
            Dict with success message

        Raises:
            HTTPException: If engine not found or deletion fails
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
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.workspace_id == workspace_id,
                        CognitionEngineModel.id == cognition_engine_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognition engine with ID '{cognition_engine_id}' not found in this workspace",
                    )

                # Soft delete by setting deleted_at timestamp
                engine.deleted_at = datetime.now(timezone.utc)
                engine.updated_by = user_id
                engine.updated_at = datetime.now(timezone.utc)

                session.commit()

                # Update all CFN configs since engines are workspace-scoped
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_all_cfns()

                return {
                    "message": f"Cognition engine '{cognition_engine_id}' deleted successfully",
                    "id": cognition_engine_id,
                }

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete cognition engine: {str(e)}",
            )


# Singleton instance
cognition_engine_service = CognitionEngineService()
