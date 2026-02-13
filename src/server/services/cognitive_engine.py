"""Cognitive Engine service - Business logic for Cognitive Engine operations"""

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognitive_engine import CognitiveEngine as CognitiveEngineModel
from server.schemas.cognitive_engine import CognitiveEngineList, CognitiveEngineListItem


class CognitiveEngineService:
    """Service layer for Cognitive Engine business logic"""

    def list_dummy(self, workspace_id: str) -> CognitiveEngineList:
        """Dummy implementation for listing cognitive engines"""
        dummy_engine = CognitiveEngineListItem(
            cognitive_engine_id="dummy-id",
            workspace_id=workspace_id,
            cognitive_engine_name="Dummy Cognitive Engine",
            config={"type": "dummy", "version": "1.0"},
            enabled=True,
            created_at="2024-01-01T00:00:00Z",
        )
        return CognitiveEngineList(engines=[dummy_engine], total=1)

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


# Singleton instance
cognitive_engine_service = CognitiveEngineService()
