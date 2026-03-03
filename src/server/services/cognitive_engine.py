"""Cognitive Engine service - Business logic for Cognitive Engine operations"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognitive_engine import CognitiveEngine as CognitiveEngineModel
from server.schemas.cognitive_engine import (
    CognitiveEngineCreate,
    CognitiveEngineDetail,
    CognitiveEngineList,
    CognitiveEngineListItem,
    CognitiveEngineUpdate,
)
from server.utils import generate_uuid


class CognitiveEngineService:
    """Service layer for Cognitive Engine business logic"""

    def create(self, workspace_id: str, engine_data: CognitiveEngineCreate, user_id: str) -> CognitiveEngineDetail:
        """
        Create a new Cognitive Engine

        Args:
            workspace_id: Workspace identifier
            engine_data: Cognitive engine creation data
            user_id: ID of the user creating the engine

        Returns:
            CognitiveEngineDetail with the created engine

        Raises:
            HTTPException: If engine with same name already exists in workspace or creation fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if engine with same name already exists in this workspace
                existing_engine = (
                    session.query(CognitiveEngineModel)
                    .filter(
                        CognitiveEngineModel.workspace_id == workspace_id,
                        CognitiveEngineModel.cognitive_engine_name == engine_data.cognitive_engine_name,
                        CognitiveEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing_engine:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Cognitive engine with name '{engine_data.cognitive_engine_name}' "
                            f"already exists in this workspace"
                        ),
                    )

                # Generate unique ID for the engine
                cognitive_engine_id = generate_uuid()

                # Create new engine
                new_engine = CognitiveEngineModel(
                    cognitive_engine_id=cognitive_engine_id,
                    workspace_id=workspace_id,
                    cognitive_engine_name=engine_data.cognitive_engine_name,
                    config=engine_data.config,
                    enabled=True,
                    created_by=user_id,
                )

                session.add(new_engine)
                session.commit()
                session.refresh(new_engine)

                return CognitiveEngineDetail(
                    cognitive_engine_id=new_engine.cognitive_engine_id,
                    workspace_id=new_engine.workspace_id,
                    cognitive_engine_name=new_engine.cognitive_engine_name,
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
                detail=f"Failed to create cognitive engine: {str(e)}",
            )

    def get(self, workspace_id: str, cognitive_engine_id: str) -> CognitiveEngineDetail:
        """
        Get a specific Cognitive Engine by ID

        Args:
            workspace_id: Workspace identifier
            cognitive_engine_id: ID of the cognitive engine

        Returns:
            CognitiveEngineDetail with the engine details

        Raises:
            HTTPException: If engine not found
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitiveEngineModel)
                    .filter(
                        CognitiveEngineModel.workspace_id == workspace_id,
                        CognitiveEngineModel.cognitive_engine_id == cognitive_engine_id,
                        CognitiveEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognitive engine with ID '{cognitive_engine_id}' not found in this workspace",
                    )

                return CognitiveEngineDetail(
                    cognitive_engine_id=engine.cognitive_engine_id,
                    workspace_id=engine.workspace_id,
                    cognitive_engine_name=engine.cognitive_engine_name,
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
                detail=f"Failed to get cognitive engine: {str(e)}",
            )

    def list(self, workspace_id: str) -> CognitiveEngineList:
        """
        List all Cognitive Engines in workspace

        Args:
            workspace_id: Workspace identifier

        Returns:
            CognitiveEngineList with engines and total count
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Query all enabled engines in workspace
                engines = (
                    session.query(CognitiveEngineModel)
                    .filter(
                        CognitiveEngineModel.workspace_id == workspace_id,
                        CognitiveEngineModel.deleted_at.is_(None),
                        CognitiveEngineModel.enabled.is_(True),
                    )
                    .all()
                )

                engine_list = [
                    CognitiveEngineListItem(
                        cognitive_engine_id=engine.cognitive_engine_id,
                        workspace_id=engine.workspace_id,
                        cognitive_engine_name=engine.cognitive_engine_name,
                        config=engine.config,
                        enabled=engine.enabled,
                        created_at=engine.created_at.isoformat() if engine.created_at else None,
                    )
                    for engine in engines
                ]

                return CognitiveEngineList(engines=engine_list, total=len(engine_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list cognitive engines: {str(e)}",
            )

    def update(
        self, workspace_id: str, cognitive_engine_id: str, update_data: CognitiveEngineUpdate, user_id: str
    ) -> CognitiveEngineDetail:
        """
        Update a Cognitive Engine

        Args:
            workspace_id: Workspace identifier
            cognitive_engine_id: ID of the cognitive engine to update
            update_data: Cognitive engine update data
            user_id: ID of the user updating the engine

        Returns:
            CognitiveEngineDetail with the updated engine

        Raises:
            HTTPException: If engine not found or update fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitiveEngineModel)
                    .filter(
                        CognitiveEngineModel.workspace_id == workspace_id,
                        CognitiveEngineModel.cognitive_engine_id == cognitive_engine_id,
                        CognitiveEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognitive engine with ID '{cognitive_engine_id}' not found in this workspace",
                    )

                # Update fields if provided
                if update_data.cognitive_engine_name is not None:
                    engine.cognitive_engine_name = update_data.cognitive_engine_name
                if update_data.config is not None:
                    engine.config = update_data.config
                if update_data.enabled is not None:
                    engine.enabled = update_data.enabled

                engine.updated_by = user_id
                engine.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(engine)

                return CognitiveEngineDetail(
                    cognitive_engine_id=engine.cognitive_engine_id,
                    workspace_id=engine.workspace_id,
                    cognitive_engine_name=engine.cognitive_engine_name,
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
                detail=f"Failed to update cognitive engine: {str(e)}",
            )

    def delete(self, workspace_id: str, cognitive_engine_id: str, user_id: str) -> dict:
        """
        Soft delete a Cognitive Engine

        Args:
            workspace_id: Workspace identifier
            cognitive_engine_id: ID of the cognitive engine to delete
            user_id: ID of the user deleting the engine

        Returns:
            Dict with success message

        Raises:
            HTTPException: If engine not found or deletion fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitiveEngineModel)
                    .filter(
                        CognitiveEngineModel.workspace_id == workspace_id,
                        CognitiveEngineModel.cognitive_engine_id == cognitive_engine_id,
                        CognitiveEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognitive engine with ID '{cognitive_engine_id}' not found in this workspace",
                    )

                # Soft delete by setting deleted_at timestamp
                engine.deleted_at = datetime.now(timezone.utc)
                engine.updated_by = user_id
                engine.updated_at = datetime.now(timezone.utc)

                session.commit()

                return {
                    "message": f"Cognitive engine '{cognitive_engine_id}' deleted successfully",
                    "cognitive_engine_id": cognitive_engine_id,
                }

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete cognitive engine: {str(e)}",
            )


# Singleton instance
cognitive_engine_service = CognitiveEngineService()
