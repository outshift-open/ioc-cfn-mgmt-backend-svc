"""Cognitive Agent service - Business logic for Cognitive Agent operations"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognitive_agent import CognitiveAgent as CognitiveAgentModel
from server.schemas.cognitive_agent import (
    CognitiveAgentCreate,
    CognitiveAgentDetail,
    CognitiveAgentList,
    CognitiveAgentListItem,
    CognitiveAgentUpdate,
)


class CognitiveAgentService:
    """Service layer for Cognitive Agent business logic"""

    def create(self, workspace_id: str, agent_data: CognitiveAgentCreate, user_id: str) -> CognitiveAgentDetail:
        """
        Create a new Cognitive Agent

        Args:
            workspace_id: Workspace identifier
            agent_data: Cognitive agent creation data
            user_id: ID of the user creating the agent

        Returns:
            CognitiveAgentDetail with the created agent

        Raises:
            HTTPException: If agent with same name already exists in workspace or creation fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if agent with same name already exists in this workspace
                existing_agent = (
                    session.query(CognitiveAgentModel)
                    .filter(
                        CognitiveAgentModel.workspace_id == workspace_id,
                        CognitiveAgentModel.cognitive_agent_name == agent_data.cognitive_agent_name,
                        CognitiveAgentModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing_agent:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Cognitive agent with name '{agent_data.cognitive_agent_name}' "
                            f"already exists in this workspace"
                        ),
                    )

                # Generate unique ID for the agent
                cognitive_agent_id = str(uuid.uuid4())

                # Create new agent
                new_agent = CognitiveAgentModel(
                    cognitive_agent_id=cognitive_agent_id,
                    workspace_id=workspace_id,
                    cognitive_agent_name=agent_data.cognitive_agent_name,
                    description=agent_data.description,
                    config=agent_data.config,
                    enabled=True,
                    created_by=user_id,
                )

                session.add(new_agent)
                session.commit()
                session.refresh(new_agent)

                return CognitiveAgentDetail(
                    cognitive_agent_id=new_agent.cognitive_agent_id,
                    workspace_id=new_agent.workspace_id,
                    cognitive_agent_name=new_agent.cognitive_agent_name,
                    description=new_agent.description,
                    config=new_agent.config,
                    enabled=new_agent.enabled,
                    created_at=new_agent.created_at,
                    updated_at=new_agent.updated_at,
                    created_by=new_agent.created_by,
                    updated_by=new_agent.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create cognitive agent: {str(e)}",
            )

    def get(self, workspace_id: str, cognitive_agent_id: str) -> CognitiveAgentDetail:
        """
        Get a specific Cognitive Agent by ID

        Args:
            workspace_id: Workspace identifier
            cognitive_agent_id: ID of the cognitive agent

        Returns:
            CognitiveAgentDetail with the agent details

        Raises:
            HTTPException: If agent not found
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                agent = (
                    session.query(CognitiveAgentModel)
                    .filter(
                        CognitiveAgentModel.workspace_id == workspace_id,
                        CognitiveAgentModel.cognitive_agent_id == cognitive_agent_id,
                        CognitiveAgentModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not agent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognitive agent with ID '{cognitive_agent_id}' not found in this workspace",
                    )

                return CognitiveAgentDetail(
                    cognitive_agent_id=agent.cognitive_agent_id,
                    workspace_id=agent.workspace_id,
                    cognitive_agent_name=agent.cognitive_agent_name,
                    description=agent.description,
                    config=agent.config,
                    enabled=agent.enabled,
                    created_at=agent.created_at,
                    updated_at=agent.updated_at,
                    created_by=agent.created_by,
                    updated_by=agent.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get cognitive agent: {str(e)}",
            )

    def list(self, workspace_id: str) -> CognitiveAgentList:
        """
        List all Cognitive Agents in workspace

        Args:
            workspace_id: Workspace identifier

        Returns:
            CognitiveAgentList with agents and total count
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Query all enabled agents in workspace
                agents = (
                    session.query(CognitiveAgentModel)
                    .filter(
                        CognitiveAgentModel.workspace_id == workspace_id,
                        CognitiveAgentModel.deleted_at.is_(None),
                        CognitiveAgentModel.enabled.is_(True),
                    )
                    .all()
                )

                agent_list = [
                    CognitiveAgentListItem(
                        cognitive_agent_id=agent.cognitive_agent_id,
                        workspace_id=agent.workspace_id,
                        cognitive_agent_name=agent.cognitive_agent_name,
                        description=agent.description,
                        config=agent.config,
                        enabled=agent.enabled,
                        created_at=agent.created_at,
                    )
                    for agent in agents
                ]

                return CognitiveAgentList(agents=agent_list, total=len(agent_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list cognitive agents: {str(e)}",
            )

    def update(
        self, workspace_id: str, cognitive_agent_id: str, update_data: CognitiveAgentUpdate, user_id: str
    ) -> CognitiveAgentDetail:
        """
        Update a Cognitive Agent

        Args:
            workspace_id: Workspace identifier
            cognitive_agent_id: ID of the cognitive agent to update
            update_data: Cognitive agent update data
            user_id: ID of the user updating the agent

        Returns:
            CognitiveAgentDetail with the updated agent

        Raises:
            HTTPException: If agent not found or update fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                agent = (
                    session.query(CognitiveAgentModel)
                    .filter(
                        CognitiveAgentModel.workspace_id == workspace_id,
                        CognitiveAgentModel.cognitive_agent_id == cognitive_agent_id,
                        CognitiveAgentModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not agent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognitive agent with ID '{cognitive_agent_id}' not found in this workspace",
                    )

                # Update fields if provided
                if update_data.cognitive_agent_name is not None:
                    agent.cognitive_agent_name = update_data.cognitive_agent_name
                if update_data.description is not None:
                    agent.description = update_data.description
                if update_data.config is not None:
                    agent.config = update_data.config
                if update_data.enabled is not None:
                    agent.enabled = update_data.enabled

                agent.updated_by = user_id
                agent.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(agent)

                return CognitiveAgentDetail(
                    cognitive_agent_id=agent.cognitive_agent_id,
                    workspace_id=agent.workspace_id,
                    cognitive_agent_name=agent.cognitive_agent_name,
                    description=agent.description,
                    config=agent.config,
                    enabled=agent.enabled,
                    created_at=agent.created_at,
                    updated_at=agent.updated_at,
                    created_by=agent.created_by,
                    updated_by=agent.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update cognitive agent: {str(e)}",
            )

    def delete(self, workspace_id: str, cognitive_agent_id: str, user_id: str) -> dict:
        """
        Soft delete a Cognitive Agent

        Args:
            workspace_id: Workspace identifier
            cognitive_agent_id: ID of the cognitive agent to delete
            user_id: ID of the user deleting the agent

        Returns:
            Dict with success message

        Raises:
            HTTPException: If agent not found or deletion fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                agent = (
                    session.query(CognitiveAgentModel)
                    .filter(
                        CognitiveAgentModel.workspace_id == workspace_id,
                        CognitiveAgentModel.cognitive_agent_id == cognitive_agent_id,
                        CognitiveAgentModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not agent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognitive agent with ID '{cognitive_agent_id}' not found in this workspace",
                    )

                # Soft delete by setting deleted_at timestamp
                agent.deleted_at = datetime.now(timezone.utc)
                agent.updated_by = user_id
                agent.updated_at = datetime.now(timezone.utc)

                session.commit()

                return {
                    "message": f"Cognitive agent '{cognitive_agent_id}' deleted successfully",
                    "cognitive_agent_id": cognitive_agent_id,
                }

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete cognitive agent: {str(e)}",
            )


# Singleton instance
cognitive_agent_service = CognitiveAgentService()
