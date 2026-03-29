# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Multi-Agentic System (MAS) service - Business logic for MAS operations"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from server.schemas.multi_agentic_system import (
    MultiAgenticSystemRequest,
    MultiAgenticSystemUpdate,
    MultiAgenticSystemResponse,
    MultiAgenticSystem as MultiAgenticSystemSchema,
    MultiAgenticSystems,
    AgentWithMemory,
)
from server.database.relational_db.models.multi_agentic_system import MultiAgenticSystem as MultiAgenticSystemModel
from server.database.relational_db.models.memory_provider import MemoryProvider as MemoryProviderModel
from server.database.relational_db.db import RelationalDB
from server.services.workspace import workspace_service
from server.services.audit import AuditEventType, ResourceType, audit_service, AuditRequest
from server.schemas.memory_provider import MemoryProviderDetail
from server.utils import generate_uuid


class MultiAgenticSystemService:
    """Service layer for MAS business logic"""

    def _enrich_with_memory_providers(self, session, mas: MultiAgenticSystemModel) -> MultiAgenticSystemSchema:
        """Enrich MAS data with full memory provider details"""

        # Fetch shared memory provider details if exists
        shared_memory = None
        if mas.shared_memory_provider_id:
            shared_provider = (
                session.query(MemoryProviderModel)
                .filter(
                    MemoryProviderModel.memory_provider_id == mas.shared_memory_provider_id,
                    MemoryProviderModel.deleted_at.is_(None),
                )
                .first()
            )
            if shared_provider:
                shared_memory = MemoryProviderDetail(
                    memory_provider_id=shared_provider.memory_provider_id,
                    memory_provider_name=shared_provider.memory_provider_name,
                    description=shared_provider.description,
                    config=shared_provider.config,
                    enabled=shared_provider.enabled,
                    created_at=shared_provider.created_at,
                    updated_at=shared_provider.updated_at,
                    created_by=shared_provider.created_by,
                    updated_by=shared_provider.updated_by,
                )

        # Enrich agents with memory provider details
        enriched_agents = None
        if mas.agents:
            enriched_agents = []
            for agent in mas.agents:
                agentic_memory = None
                agent_memory_id = agent.get("agentic_memory_provider_id")

                if agent_memory_id:
                    agent_provider = (
                        session.query(MemoryProviderModel)
                        .filter(
                            MemoryProviderModel.memory_provider_id == agent_memory_id,
                            MemoryProviderModel.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if agent_provider:
                        agentic_memory = MemoryProviderDetail(
                            memory_provider_id=agent_provider.memory_provider_id,
                            memory_provider_name=agent_provider.memory_provider_name,
                            description=agent_provider.description,
                            config=agent_provider.config,
                            enabled=agent_provider.enabled,
                            created_at=agent_provider.created_at,
                            updated_at=agent_provider.updated_at,
                            created_by=agent_provider.created_by,
                            updated_by=agent_provider.updated_by,
                        )

                enriched_agents.append(
                    AgentWithMemory(
                        agent_id=agent.get("agent_id"),
                        agentic_memory=agentic_memory,
                        config=agent.get("config"),
                    )
                )

        return MultiAgenticSystemSchema(
            id=mas.id,
            workspace_id=mas.workspace_id,
            name=mas.name,
            description=mas.description,
            shared_memory=shared_memory,
            agents=enriched_agents,
            config=mas.config,
            created_at=mas.created_at,
            updated_at=mas.updated_at,
            created_by=mas.created_by,
            updated_by=mas.updated_by,
        )

    def create(self, workspace_id: str, mas_data: MultiAgenticSystemRequest) -> MultiAgenticSystemResponse:
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
                # Prevent duplicate active MAS names within the same workspace
                existing = (
                    session.query(MultiAgenticSystemModel)
                    .filter(
                        MultiAgenticSystemModel.workspace_id == workspace_id,
                        MultiAgenticSystemModel.name == mas_data.name,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .first()
                )
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Multi-agentic system with name '{mas_data.name}' already exists in this workspace",
                    )

                # Convert agents from Pydantic models to dict for JSONB storage
                agents_json = None
                if mas_data.agents:
                    agents_json = [agent.model_dump() for agent in mas_data.agents]

                new_mas = MultiAgenticSystemModel(
                    id=generate_uuid(),
                    workspace_id=workspace_id,
                    name=mas_data.name,
                    description=mas_data.description,
                    shared_memory_provider_id=mas_data.shared_memory_provider_id,
                    agents=agents_json,
                    config=mas_data.config,
                )

                session.add(new_mas)
                session.commit()
                session.refresh(new_mas)

                response = MultiAgenticSystemResponse(
                    id=new_mas.id,
                    name=new_mas.name,
                )

                # Update CFN config for this workspace
                from server.services.cognition_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_workspace(workspace_id)

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.MAS,
                        audit_type=AuditEventType.RESOURCE_CREATED,
                        audit_resource_id=new_mas.id,
                        created_by="",  # TODO: get user from apikey
                        audit_information=mas_data.model_dump(),
                        audit_extra_information="success",
                        created_at=new_mas.created_at,
                    )
                )

                return response

            except IntegrityError as e:
                session.rollback()
                if "idx_mas_workspace_name_unique" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Multi-agentic system with name '{mas_data.name}' already exists in this workspace",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database integrity error: {str(e)}",
                )
            except HTTPException:
                session.rollback()
                # Preserve specific HTTP error codes/messages (e.g., 409 duplicate)
                raise
            except Exception as e:
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create multi-agentic system: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create multi-agentic system: {str(e)}",
            )

    def list(self, workspace_id: str) -> MultiAgenticSystems:
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
                systems = (
                    session.query(MultiAgenticSystemModel)
                    .filter(
                        MultiAgenticSystemModel.workspace_id == workspace_id,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .all()
                )

                system_responses = [self._enrich_with_memory_providers(session, system) for system in systems]

                return MultiAgenticSystems(systems=system_responses)

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve multi-agentic systems: {str(e)}",
            )

    def get(self, workspace_id: str, mas_id: str) -> MultiAgenticSystemSchema:
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                mas = (
                    session.query(MultiAgenticSystemModel)
                    .filter(
                        MultiAgenticSystemModel.id == mas_id,
                        MultiAgenticSystemModel.workspace_id == workspace_id,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not mas:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Multi-agentic system not found",
                    )

                return self._enrich_with_memory_providers(session, mas)

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve multi-agentic system: {str(e)}",
            )

    def update(self, workspace_id: str, mas_id: str, mas_data: MultiAgenticSystemUpdate) -> MultiAgenticSystemSchema:
        """Update a multi-agentic system"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the MAS
                mas = (
                    session.query(MultiAgenticSystemModel)
                    .filter(
                        MultiAgenticSystemModel.id == mas_id,
                        MultiAgenticSystemModel.workspace_id == workspace_id,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not mas:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Multi-agentic system not found",
                    )

                # Update only provided fields
                if mas_data.name is not None:
                    # Check for duplicate name in the same workspace
                    existing = (
                        session.query(MultiAgenticSystemModel)
                        .filter(
                            MultiAgenticSystemModel.workspace_id == workspace_id,
                            MultiAgenticSystemModel.name == mas_data.name,
                            MultiAgenticSystemModel.id != mas_id,
                            MultiAgenticSystemModel.deleted_at.is_(None),
                        )
                        .first()
                    )
                    if existing:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Multi-agentic system with name '{mas_data.name}' already exists in this workspace",
                        )
                    mas.name = mas_data.name

                if mas_data.description is not None:
                    mas.description = mas_data.description

                if mas_data.shared_memory_provider_id is not None:
                    mas.shared_memory_provider_id = mas_data.shared_memory_provider_id

                if mas_data.agents is not None:
                    # Convert agents from Pydantic models to dict for JSONB storage
                    mas.agents = [agent.model_dump() for agent in mas_data.agents]

                if mas_data.config is not None:
                    mas.config = mas_data.config

                mas.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(mas)

                # Update CFN config for this workspace
                from server.services.cognition_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_workspace(workspace_id)

                response = self._enrich_with_memory_providers(session, mas)

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.MAS,
                        audit_type=AuditEventType.RESOURCE_UPDATED,
                        audit_resource_id=mas_id,
                        updated_by="",  # TODO: get user from apikey
                        audit_information=mas_data.model_dump(),
                        audit_extra_information="success",
                        updated_at=mas.updated_at,
                    )
                )

                return response

            except IntegrityError as e:
                session.rollback()
                if "idx_mas_workspace_name_unique" in str(e):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Multi-agentic system with name '{mas_data.name}' already exists in this workspace",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Database integrity error: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update multi-agentic system: {str(e)}",
            )

    def delete(self, workspace_id: str, mas_id: str, _purge: bool = False) -> dict:
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find the MAS
                mas = (
                    session.query(MultiAgenticSystemModel)
                    .filter(
                        MultiAgenticSystemModel.id == mas_id,
                        MultiAgenticSystemModel.workspace_id == workspace_id,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not mas:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Multi-agentic system not found",
                    )

                if _purge:
                    session.delete(mas)
                    message = "Multi-agentic system permanently deleted"
                else:
                    mas.deleted_at = datetime.now(timezone.utc)
                    message = "Multi-agentic system deleted successfully"

                session.commit()

                # Update CFN config for this workspace
                from server.services.cognition_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_workspace(workspace_id)

                # add to audits table
                audit_service.create_audit(
                    AuditRequest(
                        resource_type=ResourceType.MAS,
                        audit_type=AuditEventType.RESOURCE_DELETED,
                        audit_resource_id=mas_id,
                        deleted_by="",  # TODO: get user from apikey
                        audit_information={"purge": _purge},
                        audit_extra_information=message,
                        deleted_at=mas.deleted_at,
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
                detail=f"Failed to delete multi-agentic system: {str(e)}",
            )


# Global service instance
multi_agentic_system_service = MultiAgenticSystemService()
