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
    AgentIdentity,
    MASQueryByIdentity,
    MasCognitionEngineItem,
)
from server.database.relational_db.models.multi_agentic_system import MultiAgenticSystem as MultiAgenticSystemModel
from server.database.relational_db.models.agent import Agent as AgentModel
from server.database.relational_db.models.memory_provider import MemoryProvider as MemoryProviderModel
from server.database.relational_db.db import RelationalDB
from server.services.workspace import workspace_service
from server.schemas.memory_provider import MemoryProviderDetail
from server.utils import generate_uuid


class MultiAgenticSystemService:
    """Service layer for MAS business logic"""

    def _build_memory_detail(self, provider) -> MemoryProviderDetail:
        return MemoryProviderDetail(
            id=provider.id,
            name=provider.name,
            description=provider.description,
            config=provider.config,
            enabled=provider.enabled,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            created_by=provider.created_by,
            updated_by=provider.updated_by,
        )

    def _agent_row_to_schema(self, agent_row: AgentModel, provider_map: dict) -> AgentWithMemory:
        agentic_memory = None
        if agent_row.agentic_memory_provider_id and agent_row.agentic_memory_provider_id in provider_map:
            agentic_memory = self._build_memory_detail(provider_map[agent_row.agentic_memory_provider_id])

        identity = None
        if agent_row.identity_type:
            identity = AgentIdentity(
                type=agent_row.identity_type,
                identifiers=agent_row.identity_identifiers or {},
            )

        return AgentWithMemory(
            agent_id=agent_row.agent_id,
            name=agent_row.name,
            url=agent_row.url,
            identity=identity,
            agentic_memory=agentic_memory,
            config=agent_row.config,
        )

    def _enrich_mas(
        self,
        mas: MultiAgenticSystemModel,
        agents: list,
        provider_map: dict,
        ce_associations: list = None,
    ) -> MultiAgenticSystemSchema:
        shared_memory = None
        if mas.shared_memory_provider_id and mas.shared_memory_provider_id in provider_map:
            shared_memory = self._build_memory_detail(provider_map[mas.shared_memory_provider_id])

        enriched_agents = [self._agent_row_to_schema(a, provider_map) for a in agents] if agents is not None else None

        return MultiAgenticSystemSchema(
            id=mas.id,
            workspace_id=mas.workspace_id,
            name=mas.name,
            description=mas.description,
            shared_memory=shared_memory,
            agents=enriched_agents,
            config=mas.config,
            cognition_engines=ce_associations or [],
            created_at=mas.created_at,
            updated_at=mas.updated_at,
            created_by=mas.created_by,
            updated_by=mas.updated_by,
        )

    def _save_agents(self, session, mas_id: str, agents_data) -> list:
        """Create agent rows from AgentConfig list. Returns the created AgentModel instances."""
        if not agents_data:
            return []

        # Assign server-generated UUIDs where agent_id is not provided
        for agent_cfg in agents_data:
            if not agent_cfg.agent_id:
                agent_cfg.agent_id = generate_uuid()

        # Validate no duplicate agent_ids
        seen_ids = set()
        for agent_cfg in agents_data:
            if agent_cfg.agent_id in seen_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Duplicate agent_id in request: '{agent_cfg.agent_id}'",
                )
            seen_ids.add(agent_cfg.agent_id)

        # Validate no duplicate agent names within the same MAS
        seen_names = set()
        for agent_cfg in agents_data:
            if agent_cfg.name:
                if agent_cfg.name in seen_names:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Duplicate agent name in request: '{agent_cfg.name}'",
                    )
                seen_names.add(agent_cfg.name)

        agent_rows = []
        for agent_cfg in agents_data:
            identity_type = None
            identity_identifiers = None
            if agent_cfg.identity:
                identity_type = agent_cfg.identity.type if agent_cfg.identity.type else None
                identity_identifiers = agent_cfg.identity.identifiers

            row = AgentModel(
                mas_id=mas_id,
                agent_id=agent_cfg.agent_id,
                name=agent_cfg.name,
                url=agent_cfg.url,
                identity_type=identity_type,
                identity_identifiers=identity_identifiers,
                agentic_memory_provider_id=agent_cfg.agentic_memory_provider_id,
                config=agent_cfg.config,
            )
            session.add(row)
            agent_rows.append(row)

        return agent_rows

    def _sync_agents(self, session, mas_id: str, incoming_agents) -> None:
        """Diff-based agent sync: insert new, update existing, hard-delete removed."""
        now = datetime.now(timezone.utc)

        # Assign server-generated UUIDs where agent_id is not provided
        for agent_cfg in incoming_agents:
            if not agent_cfg.agent_id:
                agent_cfg.agent_id = generate_uuid()

        # Validate no duplicate agent_ids in incoming list
        seen_ids = set()
        for agent_cfg in incoming_agents:
            if agent_cfg.agent_id in seen_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Duplicate agent_id in request: '{agent_cfg.agent_id}'",
                )
            seen_ids.add(agent_cfg.agent_id)

        # Validate no duplicate agent names within the same MAS
        seen_names = set()
        for agent_cfg in incoming_agents:
            if agent_cfg.name:
                if agent_cfg.name in seen_names:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Duplicate agent name in request: '{agent_cfg.name}'",
                    )
                seen_names.add(agent_cfg.name)

        existing_rows = session.query(AgentModel).filter(AgentModel.mas_id == mas_id).all()
        existing_map = {row.agent_id: row for row in existing_rows}

        incoming_ids = set()
        for agent_cfg in incoming_agents:
            incoming_ids.add(agent_cfg.agent_id)

            identity_type = None
            identity_identifiers = None
            if agent_cfg.identity:
                identity_type = agent_cfg.identity.type if agent_cfg.identity.type else None
                identity_identifiers = agent_cfg.identity.identifiers

            if agent_cfg.agent_id in existing_map:
                row = existing_map[agent_cfg.agent_id]
                row.name = agent_cfg.name
                row.url = agent_cfg.url
                row.identity_type = identity_type
                row.identity_identifiers = identity_identifiers
                row.agentic_memory_provider_id = agent_cfg.agentic_memory_provider_id
                row.config = agent_cfg.config
                row.updated_at = now
            else:
                row = AgentModel(
                    mas_id=mas_id,
                    agent_id=agent_cfg.agent_id,
                    name=agent_cfg.name,
                    url=agent_cfg.url,
                    identity_type=identity_type,
                    identity_identifiers=identity_identifiers,
                    agentic_memory_provider_id=agent_cfg.agentic_memory_provider_id,
                    config=agent_cfg.config,
                )
                session.add(row)

        # Hard-delete agents removed from the incoming list
        for agent_id, row in existing_map.items():
            if agent_id not in incoming_ids:
                session.delete(row)

    def create(
        self, workspace_id: str, mas_data: MultiAgenticSystemRequest, user_id: str = "system"
    ) -> MultiAgenticSystemResponse:
        if not workspace_service.exists(workspace_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
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

                new_mas = MultiAgenticSystemModel(
                    id=generate_uuid(),
                    workspace_id=workspace_id,
                    name=mas_data.name,
                    description=mas_data.description,
                    shared_memory_provider_id=mas_data.shared_memory_provider_id,
                    agents=None,
                    config=mas_data.config,
                )

                session.add(new_mas)
                session.flush()

                self._save_agents(session, new_mas.id, mas_data.agents)

                session.commit()
                session.refresh(new_mas)

                response = MultiAgenticSystemResponse(
                    id=new_mas.id,
                    name=new_mas.name,
                )

                from server.database.relational_db.models.workspace import Workspace

                workspace = session.query(Workspace).filter(Workspace.id == workspace_id).first()
                workspace_cfn_id = workspace.cfn_id if workspace else None

                from server.services.vector_store_cfn import vector_store_cfn_service

                vector_store_cfn_service.onboard_vector_store(workspace_id, new_mas.id)

                from server.services.cognition_engine import cognition_engine_service

                cognition_engine_service.auto_attach_for_new_mas(new_mas.id, workspace_cfn_id)

                for ce_id in mas_data.cognition_engine_ids or []:
                    try:
                        cognition_engine_service.associate(new_mas.id, ce_id, user_id)
                    except HTTPException as e:
                        if e.status_code != status.HTTP_409_CONFLICT:
                            raise

                # Regenerate config after all CE associations are committed
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_workspace(workspace_id)

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

                mas_ids = [mas.id for mas in systems]

                # Batch fetch all active agents for these MAS
                all_agents = []
                if mas_ids:
                    all_agents = session.query(AgentModel).filter(AgentModel.mas_id.in_(mas_ids)).all()

                # Group agents by mas_id
                agents_by_mas = {}
                for agent in all_agents:
                    agents_by_mas.setdefault(agent.mas_id, []).append(agent)

                # Collect all unique memory provider IDs
                provider_ids = set()
                for mas in systems:
                    if mas.shared_memory_provider_id:
                        provider_ids.add(mas.shared_memory_provider_id)
                for agent in all_agents:
                    if agent.agentic_memory_provider_id:
                        provider_ids.add(agent.agentic_memory_provider_id)

                provider_map = {}
                if provider_ids:
                    providers = (
                        session.query(MemoryProviderModel)
                        .filter(
                            MemoryProviderModel.id.in_(provider_ids),
                            MemoryProviderModel.deleted_at.is_(None),
                        )
                        .all()
                    )
                    provider_map = {p.id: p for p in providers}

                from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
                from server.database.relational_db.models.cognition_engine import (
                    CognitionEngine as CognitionEngineModel,
                )

                ce_by_mas = {}
                if mas_ids:
                    ce_rows = (
                        session.query(MasCognitionEngine, CognitionEngineModel)
                        .join(CognitionEngineModel, MasCognitionEngine.ce_id == CognitionEngineModel.id)
                        .filter(MasCognitionEngine.mas_id.in_(mas_ids))
                        .all()
                    )
                    for junc, ce in ce_rows:
                        ce_by_mas.setdefault(junc.mas_id, []).append(
                            MasCognitionEngineItem(
                                ce_id=junc.ce_id,
                                name=ce.name,
                                kinds_subkinds=ce.kinds_subkinds,
                                subprotocols=ce.subprotocols,
                                category=ce.category,
                                url=ce.url,
                                enabled=ce.enabled,
                                status=ce.status,
                                mas_config=junc.mas_config,
                            )
                        )

                system_responses = [
                    self._enrich_mas(mas, agents_by_mas.get(mas.id, []), provider_map, ce_by_mas.get(mas.id, []))
                    for mas in systems
                ]

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

                agents = session.query(AgentModel).filter(AgentModel.mas_id == mas_id).all()

                # Collect provider IDs
                provider_ids = set()
                if mas.shared_memory_provider_id:
                    provider_ids.add(mas.shared_memory_provider_id)
                for agent in agents:
                    if agent.agentic_memory_provider_id:
                        provider_ids.add(agent.agentic_memory_provider_id)

                provider_map = {}
                if provider_ids:
                    providers = (
                        session.query(MemoryProviderModel)
                        .filter(
                            MemoryProviderModel.id.in_(provider_ids),
                            MemoryProviderModel.deleted_at.is_(None),
                        )
                        .all()
                    )
                    provider_map = {p.id: p for p in providers}

                from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
                from server.database.relational_db.models.cognition_engine import (
                    CognitionEngine as CognitionEngineModel,
                )

                ce_rows = (
                    session.query(MasCognitionEngine, CognitionEngineModel)
                    .join(CognitionEngineModel, MasCognitionEngine.ce_id == CognitionEngineModel.id)
                    .filter(MasCognitionEngine.mas_id == mas_id)
                    .all()
                )
                ce_associations = [
                    MasCognitionEngineItem(
                        ce_id=junc.ce_id,
                        name=ce.name,
                        kinds_subkinds=ce.kinds_subkinds,
                        subprotocols=ce.subprotocols,
                        category=ce.category,
                        url=ce.url,
                        enabled=ce.enabled,
                        status=ce.status,
                        mas_config=junc.mas_config,
                    )
                    for junc, ce in ce_rows
                ]

                return self._enrich_mas(mas, agents, provider_map, ce_associations)

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve multi-agentic system: {str(e)}",
            )

    def update(
        self, workspace_id: str, mas_id: str, mas_data: MultiAgenticSystemUpdate, user_id: str = "system"
    ) -> MultiAgenticSystemSchema:
        """Update a multi-agentic system"""
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

                if mas_data.name is not None:
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
                    self._sync_agents(session, mas_id, mas_data.agents)
                    mas.agents = None

                if mas_data.config is not None:
                    mas.config = mas_data.config

                if mas_data.cognition_engine_configs is not None:
                    from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

                    for ce_id, ce_mas_config in mas_data.cognition_engine_configs.items():
                        assoc = (
                            session.query(MasCognitionEngine)
                            .filter(
                                MasCognitionEngine.mas_id == mas_id,
                                MasCognitionEngine.ce_id == ce_id,
                            )
                            .first()
                        )
                        if assoc:
                            assoc.mas_config = ce_mas_config

                mas.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(mas)

                # Re-fetch agents after sync
                agents = session.query(AgentModel).filter(AgentModel.mas_id == mas_id).all()

                provider_ids = set()
                if mas.shared_memory_provider_id:
                    provider_ids.add(mas.shared_memory_provider_id)
                for agent in agents:
                    if agent.agentic_memory_provider_id:
                        provider_ids.add(agent.agentic_memory_provider_id)

                provider_map = {}
                if provider_ids:
                    providers = (
                        session.query(MemoryProviderModel)
                        .filter(
                            MemoryProviderModel.id.in_(provider_ids),
                            MemoryProviderModel.deleted_at.is_(None),
                        )
                        .all()
                    )
                    provider_map = {p.id: p for p in providers}

                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_workspace(workspace_id)

                from server.database.relational_db.models.workspace import Workspace
                from server.services.cognition_engine import cognition_engine_service

                workspace_obj = session.query(Workspace).filter(Workspace.id == workspace_id).first()
                workspace_cfn_id = workspace_obj.cfn_id if workspace_obj else None
                cognition_engine_service.auto_attach_for_new_mas(mas.id, workspace_cfn_id)

                from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
                from server.database.relational_db.models.cognition_engine import (
                    CognitionEngine as CognitionEngineModel,
                )

                if mas_data.cognition_engine_ids is not None:
                    incoming = set(mas_data.cognition_engine_ids)
                    existing_ce_ids = {
                        row.ce_id
                        for row in session.query(MasCognitionEngine).filter(MasCognitionEngine.mas_id == mas.id)
                    }
                    for ce_id in incoming - existing_ce_ids:
                        cognition_engine_service.associate(mas.id, ce_id, user_id)
                    for ce_id in existing_ce_ids - incoming:
                        cognition_engine_service.disassociate(ce_id, mas.id, user_id)

                ce_rows = (
                    session.query(MasCognitionEngine, CognitionEngineModel)
                    .join(CognitionEngineModel, MasCognitionEngine.ce_id == CognitionEngineModel.id)
                    .filter(MasCognitionEngine.mas_id == mas.id)
                    .all()
                )
                ce_associations = [
                    MasCognitionEngineItem(
                        ce_id=junc.ce_id,
                        name=ce.name,
                        kinds_subkinds=ce.kinds_subkinds,
                        subprotocols=ce.subprotocols,
                        category=ce.category,
                        url=ce.url,
                        enabled=ce.enabled,
                        status=ce.status,
                        mas_config=junc.mas_config,
                    )
                    for junc, ce in ce_rows
                ]

                return self._enrich_mas(mas, agents, provider_map, ce_associations)

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

    def query_by_identity(self, workspace_id: str, query: MASQueryByIdentity) -> MultiAgenticSystems:
        """Find MAS that have agents with identity_type='claude' and matching identity_identifiers."""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                agent_query = (
                    session.query(AgentModel)
                    .join(
                        MultiAgenticSystemModel,
                        AgentModel.mas_id == MultiAgenticSystemModel.id,
                    )
                    .filter(
                        MultiAgenticSystemModel.workspace_id == workspace_id,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                )

                if query.identity_type:
                    agent_query = agent_query.filter(
                        AgentModel.identity_type == query.identity_type,
                    )

                if query.identity_identifiers:
                    agent_query = agent_query.filter(
                        AgentModel.identity_identifiers.contains(query.identity_identifiers),
                    )

                matching_agents = agent_query.all()

                if not matching_agents:
                    return MultiAgenticSystems(systems=[])

                mas_ids = list({a.mas_id for a in matching_agents})

                systems = (
                    session.query(MultiAgenticSystemModel)
                    .filter(
                        MultiAgenticSystemModel.id.in_(mas_ids),
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .all()
                )

                all_agents = session.query(AgentModel).filter(AgentModel.mas_id.in_(mas_ids)).all()

                agents_by_mas = {}
                for agent in all_agents:
                    agents_by_mas.setdefault(agent.mas_id, []).append(agent)

                provider_ids = set()
                for mas in systems:
                    if mas.shared_memory_provider_id:
                        provider_ids.add(mas.shared_memory_provider_id)
                for agent in all_agents:
                    if agent.agentic_memory_provider_id:
                        provider_ids.add(agent.agentic_memory_provider_id)

                provider_map = {}
                if provider_ids:
                    providers = (
                        session.query(MemoryProviderModel)
                        .filter(
                            MemoryProviderModel.id.in_(provider_ids),
                            MemoryProviderModel.deleted_at.is_(None),
                        )
                        .all()
                    )
                    provider_map = {p.id: p for p in providers}

                from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
                from server.database.relational_db.models.cognition_engine import (
                    CognitionEngine as CognitionEngineModel,
                )

                ce_by_mas = {}
                ce_rows = (
                    session.query(MasCognitionEngine, CognitionEngineModel)
                    .join(CognitionEngineModel, MasCognitionEngine.ce_id == CognitionEngineModel.id)
                    .filter(MasCognitionEngine.mas_id.in_(mas_ids))
                    .all()
                )
                for junc, ce in ce_rows:
                    ce_by_mas.setdefault(junc.mas_id, []).append(
                        MasCognitionEngineItem(
                            ce_id=junc.ce_id,
                            name=ce.name,
                            kinds_subkinds=ce.kinds_subkinds,
                            subprotocols=ce.subprotocols,
                            category=ce.category,
                            url=ce.url,
                            enabled=ce.enabled,
                            status=ce.status,
                            mas_config=junc.mas_config,
                        )
                    )

                system_responses = [
                    self._enrich_mas(mas, agents_by_mas.get(mas.id, []), provider_map, ce_by_mas.get(mas.id, []))
                    for mas in systems
                ]

                return MultiAgenticSystems(systems=system_responses)

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to query multi-agentic systems by identity: {str(e)}",
            )

    def delete(self, workspace_id: str, mas_id: str, _purge: bool = False) -> dict:
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

                now = datetime.now(timezone.utc)

                if _purge:
                    # CASCADE on FK handles agent row deletion
                    session.delete(mas)
                    message = "Multi-agentic system permanently deleted"
                else:
                    mas.deleted_at = now
                    # Hard-delete associated agents
                    session.query(AgentModel).filter(
                        AgentModel.mas_id == mas_id,
                    ).delete()
                    message = "Multi-agentic system deleted successfully"

                session.commit()

                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_workspace(workspace_id)

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
