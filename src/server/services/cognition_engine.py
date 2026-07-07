# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine service - Business logic for Cognition Engine operations"""

import copy
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognition_engine import CognitionEngine as CognitionEngineModel
from server.schemas.cognition_engine import (
    CognitionEngineAssociateResponse,
    CognitionEngineDetail,
    CognitionEngineHeartbeatResponse,
    CognitionEngineList,
    CognitionEngineListItem,
    CognitionEnginePatchRequest,
    CognitionEngineRegisterRequest,
    CognitionEngineResponse,
)

from server.utils import generate_uuid
from server.utils.encryption import process_config_for_storage

_IMMUTABLE_CE_FIELDS = {"cfn_id", "version", "name", "kind", "subkind"}


class CognitionEngineService:
    """Service layer for Cognition Engine business logic"""

    def register(
        self, engine_data: CognitionEngineRegisterRequest, user_id: str
    ) -> tuple[CognitionEngineResponse, bool]:
        """
        Register or update a Cognition Engine (idempotent upsert).

        Returns (response, created) — created=True for new, False for update.
        Raises HTTPException 404 if the CFN does not exist.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                from server.database.relational_db.models.cognition_fabric_node import CognitionFabricNode

                cfn = (
                    session.query(CognitionFabricNode)
                    .filter(
                        CognitionFabricNode.id == engine_data.cfn_id,
                        CognitionFabricNode.deleted_at.is_(None),
                    )
                    .first()
                )
                if not cfn:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cognition Fabric Node '{engine_data.cfn_id}' not found",
                    )

                existing = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.cfn_id == engine_data.cfn_id,
                        CognitionEngineModel.name == engine_data.name,
                        CognitionEngineModel.version == engine_data.version,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing:
                    existing.url = engine_data.url
                    existing.kind = engine_data.kind
                    existing.subkind = engine_data.subkind
                    existing.auth = _auth_for_storage(engine_data.auth)
                    existing.capabilities = engine_data.capabilities or []
                    existing.metrics = engine_data.metrics or []
                    existing.mas_auto_associate = engine_data.mas_auto_associate
                    existing.config = engine_data.config or {}
                    existing.mas_config = engine_data.mas_config or {}
                    existing.updated_by = user_id
                    existing.updated_at = datetime.now(timezone.utc)
                    session.commit()
                    session.refresh(existing)
                    engine, created = existing, False
                else:
                    engine = CognitionEngineModel(
                        id=generate_uuid(),
                        cfn_id=engine_data.cfn_id,
                        name=engine_data.name,
                        url=engine_data.url,
                        version=engine_data.version,
                        kind=engine_data.kind,
                        subkind=engine_data.subkind,
                        auth=_auth_for_storage(engine_data.auth),
                        capabilities=engine_data.capabilities or [],
                        metrics=engine_data.metrics or [],
                        enabled=True,
                        mas_auto_associate=engine_data.mas_auto_associate,
                        status="offline",
                        config=engine_data.config or {},
                        mas_config=engine_data.mas_config or {},
                        created_by=user_id,
                    )
                    session.add(engine)
                    session.commit()
                    session.refresh(engine)
                    created = True

                response = (
                    CognitionEngineResponse(
                        ce_id=engine.id,
                        cfn_id=engine.cfn_id,
                        name=engine.name,
                        version=engine.version,
                        kind=engine.kind,
                        subkind=engine.subkind,
                        enabled=engine.enabled,
                        mas_auto_associate=engine.mas_auto_associate,
                        status=engine.status,
                        created=created,
                    ),
                    created,
                )

            finally:
                session.close()

            from server.services.cognition_fabric_node import cognition_fabric_node_service

            cognition_fabric_node_service.update_config_for_cfn(engine_data.cfn_id)

            return response

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register cognition engine: {str(e)}",
            )

    def get(self, ce_id: str) -> CognitionEngineDetail:
        """
        Get a Cognition Engine by ID.

        Raises HTTPException 404 if not found.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.id == ce_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"CE {ce_id} not found",
                    )

                _validate_cfn_active(session, engine.cfn_id)

                return _to_detail(engine)

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get cognition engine: {str(e)}",
            )

    def list(self, cfn_id: Optional[str] = None, status: Optional[str] = None) -> CognitionEngineList:
        """
        List Cognition Engines, optionally filtered by cfn_id and/or status.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                if cfn_id is not None:
                    _validate_cfn_active(session, cfn_id)

                query = session.query(CognitionEngineModel).filter(CognitionEngineModel.deleted_at.is_(None))

                if cfn_id is not None:
                    query = query.filter(CognitionEngineModel.cfn_id == cfn_id)
                if status is not None:
                    query = query.filter(CognitionEngineModel.status == status)

                engines = query.all()

                return CognitionEngineList(
                    cognition_engines=[
                        CognitionEngineListItem(
                            id=e.id,
                            cfn_id=e.cfn_id,
                            name=e.name,
                            version=e.version,
                            kind=e.kind,
                            subkind=e.subkind,
                            url=e.url,
                            enabled=e.enabled,
                            mas_auto_associate=e.mas_auto_associate,
                            status=e.status,
                            last_seen=e.last_seen,
                            config=e.config,
                            mas_config=e.mas_config,
                            created_at=e.created_at,
                        )
                        for e in engines
                    ],
                    total=len(engines),
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list cognition engines: {str(e)}",
            )

    def delete(self, ce_id: str, user_id: str) -> None:
        """
        Soft delete a Cognition Engine by ID.

        Raises HTTPException 404 if not found.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.id == ce_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"CE {ce_id} not found",
                    )

                _validate_cfn_active(session, engine.cfn_id)

                if engine.enabled:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="CE must be disabled before it can be deleted",
                    )

                from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
                from server.database.relational_db.models.multi_agentic_system import (
                    MultiAgenticSystem as MultiAgenticSystemModel,
                )

                attached = (
                    session.query(MasCognitionEngine)
                    .join(
                        MultiAgenticSystemModel,
                        MasCognitionEngine.mas_id == MultiAgenticSystemModel.id,
                    )
                    .filter(
                        MasCognitionEngine.ce_id == ce_id,
                        MultiAgenticSystemModel.deleted_at.is_(None),
                    )
                    .count()
                )
                if attached:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="CE cannot be deleted while it is associated with one or more MAS",
                    )

                cfn_id = engine.cfn_id
                engine.deleted_at = datetime.now(timezone.utc)
                engine.updated_by = user_id
                engine.updated_at = datetime.now(timezone.utc)

                session.commit()

            finally:
                session.close()

            from server.services.cognition_fabric_node import cognition_fabric_node_service

            cognition_fabric_node_service.update_config_for_cfn(cfn_id)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete cognition engine: {str(e)}",
            )

    def heartbeat(self, ce_id: str) -> CognitionEngineHeartbeatResponse:
        """
        Update CE heartbeat: sets last_seen to now and flips offline→online.

        Raises HTTPException 404 if not found.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.id == ce_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"CE {ce_id} not found",
                    )

                _validate_cfn_active(session, engine.cfn_id)

                engine.last_seen = datetime.now(timezone.utc)
                transitioned = engine.status == "offline"
                if transitioned:
                    engine.status = "online"

                session.commit()
                session.refresh(engine)

                cfn_id = engine.cfn_id
                response = CognitionEngineHeartbeatResponse(
                    status=engine.status,
                    last_seen=engine.last_seen,
                )

            finally:
                session.close()

            if transitioned:
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_cfn(cfn_id)

            return response

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process heartbeat: {str(e)}",
            )

    def patch(self, ce_id: str, patch_data: CognitionEnginePatchRequest, user_id: str) -> CognitionEngineDetail:
        """
        Partially update a Cognition Engine.

        Raises 400 if any immutable fields are included in the request.
        Raises 404 if the CE does not exist.
        """
        provided = patch_data.model_dump(exclude_none=True)

        attempted_immutable = _IMMUTABLE_CE_FIELDS & set(provided.keys())
        if attempted_immutable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The following fields cannot be updated: {sorted(attempted_immutable)}",
            )

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.id == ce_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not engine:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"CE {ce_id} not found",
                    )

                _validate_cfn_active(session, engine.cfn_id)

                if "url" in provided:
                    engine.url = provided["url"]
                if "enabled" in provided:
                    if not provided["enabled"]:
                        from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
                        from server.database.relational_db.models.multi_agentic_system import (
                            MultiAgenticSystem as MultiAgenticSystemModel,
                        )

                        attached = (
                            session.query(MasCognitionEngine)
                            .join(
                                MultiAgenticSystemModel,
                                MasCognitionEngine.mas_id == MultiAgenticSystemModel.id,
                            )
                            .filter(
                                MasCognitionEngine.ce_id == ce_id,
                                MultiAgenticSystemModel.deleted_at.is_(None),
                            )
                            .count()
                        )
                        if attached:
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="CE cannot be disabled while it has attached MAS",
                            )
                    engine.enabled = provided["enabled"]
                if "capabilities" in provided:
                    engine.capabilities = provided["capabilities"]
                if "metrics" in provided:
                    engine.metrics = provided["metrics"]
                if "config" in provided:
                    engine.config = provided["config"]
                mas_config_updated = False
                if "mas_config" in provided:
                    from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

                    session.query(MasCognitionEngine).filter(MasCognitionEngine.ce_id == ce_id).update(
                        {"mas_config": provided["mas_config"]}, synchronize_session="fetch"
                    )
                    mas_config_updated = True
                if "auth" in provided:
                    engine.auth = _auth_for_storage(provided["auth"])
                if "mas_auto_associate" in provided:
                    engine.mas_auto_associate = provided["mas_auto_associate"]

                cfn_id = engine.cfn_id
                engine.updated_by = user_id
                engine.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(engine)

                detail = _to_detail(engine)

            finally:
                session.close()

            if mas_config_updated:
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_cfn(cfn_id)

            return detail

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update cognition engine: {str(e)}",
            )

    def associate(self, mas_id: str, ce_id: str, user_id: str) -> CognitionEngineAssociateResponse:
        """
        Associate a CE with a MAS.

        Validates:
        - CE exists and is not deleted
        - CE's CFN is active
        - MAS exists and is not deleted
        - MAS's workspace belongs to the same CFN as the CE (boundary constraint)
        - Association does not already exist
        """
        try:
            from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine
            from server.database.relational_db.models.multi_agentic_system import MultiAgenticSystem
            from server.database.relational_db.models.workspace import Workspace

            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.id == ce_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )
                if not engine:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"CE {ce_id} not found")

                _validate_cfn_active(session, engine.cfn_id)

                mas = (
                    session.query(MultiAgenticSystem)
                    .filter(
                        MultiAgenticSystem.id == mas_id,
                        MultiAgenticSystem.deleted_at.is_(None),
                    )
                    .first()
                )
                if not mas:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"MAS {mas_id} not found",
                    )

                workspace = session.query(Workspace).filter(Workspace.id == mas.workspace_id).first()
                if not workspace or workspace.cfn_id != engine.cfn_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="MAS belongs to a workspace on a different CFN than the CE",
                    )

                workspace_id = mas.workspace_id  # Capture before commit expires attributes

                existing = (
                    session.query(MasCognitionEngine)
                    .filter(
                        MasCognitionEngine.mas_id == mas_id,
                        MasCognitionEngine.ce_id == ce_id,
                    )
                    .first()
                )
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="CE is already associated with this MAS",
                    )

                association = MasCognitionEngine(
                    mas_id=mas_id,
                    ce_id=ce_id,
                    mas_config=copy.deepcopy(engine.mas_config) if engine.mas_config else None,
                    created_by=user_id,
                )
                session.add(association)
                session.commit()
                session.refresh(association)

                response = CognitionEngineAssociateResponse(
                    ce_id=ce_id,
                    mas_id=mas_id,
                    created_at=association.created_at,
                )

            finally:
                session.close()

            from server.services.cognition_fabric_node import cognition_fabric_node_service

            cognition_fabric_node_service.update_config_for_workspace(workspace_id)

            return response

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to associate cognition engine: {str(e)}",
            )

    def disassociate(self, ce_id: str, mas_id: str, user_id: str, workspace_id: Optional[str] = None) -> None:
        """
        Remove the association between a CE and a MAS.

        Raises 404 if the CE does not exist or the association does not exist.
        """
        try:
            from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

            db = RelationalDB()
            session = db.get_session()

            try:
                engine = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.id == ce_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .first()
                )
                if not engine:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"CE {ce_id} not found")

                _validate_cfn_active(session, engine.cfn_id)

                association = (
                    session.query(MasCognitionEngine)
                    .filter(
                        MasCognitionEngine.ce_id == ce_id,
                        MasCognitionEngine.mas_id == mas_id,
                    )
                    .first()
                )
                if not association:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No association found between CE {ce_id} and MAS {mas_id}",
                    )

                session.delete(association)
                session.commit()

            finally:
                session.close()

            if workspace_id:
                from server.services.cognition_fabric_node import cognition_fabric_node_service

                cognition_fabric_node_service.update_config_for_workspace(workspace_id)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to disassociate cognition engine: {str(e)}",
            )

    def list_for_cfn(self, cfn_id: str) -> list:
        """
        List Cognition Engines with raw auth for CFN consumption.

        Bypasses response masking so process_config_for_cfn() can decrypt credentials.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                engines = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.cfn_id == cfn_id,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .all()
                )

                return [
                    {
                        "id": e.id,
                        "name": e.name,
                        "url": e.url,
                        "kind": e.kind,
                        "subkind": e.subkind,
                        "enabled": e.enabled,
                        "status": e.status,
                        "last_seen": e.last_seen.isoformat() if e.last_seen else None,
                        "capabilities": e.capabilities or [],
                        "metrics": e.metrics or [],
                        "config": e.config or {},
                        "mas_config": e.mas_config or {},
                        "mas_auto_associate": e.mas_auto_associate,
                        "auth": e.auth,
                    }
                    for e in engines
                ]

            finally:
                session.close()

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to list cognition engines for CFN: {str(e)}")
            return []

    def mark_stale_engines_offline(self, threshold_minutes: int = 2) -> int:
        """
        Background job: mark engines offline if last_seen exceeds threshold.

        Returns count of engines marked offline.
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                threshold_time = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)

                stale_engines = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.status == "online",
                        CognitionEngineModel.last_seen < threshold_time,
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .all()
                )

                for engine in stale_engines:
                    engine.status = "offline"

                count = len(stale_engines)
                if count > 0:
                    session.commit()

                return count

            finally:
                session.close()

        except Exception as e:
            logging.getLogger(__name__).error(f"Error marking stale cognition engines offline: {str(e)}")
            return 0

    def auto_attach_for_new_mas(self, mas_id: str, cfn_id: str) -> None:
        """Auto-associate: on MAS create/update, associate all enabled mas_auto_associate=True CEs in the CFN."""
        if not cfn_id:
            return

        try:
            from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

            db = RelationalDB()
            session = db.get_session()

            try:
                auto_ces = (
                    session.query(CognitionEngineModel)
                    .filter(
                        CognitionEngineModel.cfn_id == cfn_id,
                        CognitionEngineModel.mas_auto_associate.is_(True),
                        CognitionEngineModel.enabled.is_(True),
                        CognitionEngineModel.deleted_at.is_(None),
                    )
                    .all()
                )

                for ce_engine in auto_ces:
                    exists = (
                        session.query(MasCognitionEngine)
                        .filter(
                            MasCognitionEngine.ce_id == ce_engine.id,
                            MasCognitionEngine.mas_id == mas_id,
                        )
                        .first()
                    )
                    if not exists:
                        session.add(
                            MasCognitionEngine(
                                mas_id=mas_id,
                                ce_id=ce_engine.id,
                                mas_config=copy.deepcopy(ce_engine.mas_config) if ce_engine.mas_config else None,
                                created_by="system",
                            )
                        )

                auto_ce_ids = [e.id for e in auto_ces]

                if auto_ce_ids:
                    session.commit()

            finally:
                session.close()

        except Exception as e:
            logging.getLogger(__name__).error(f"Auto-attach MAS {mas_id} to CEs failed: {e}")


def _validate_cfn_active(session, cfn_id: str) -> None:
    """Raise 404 if the CFN does not exist, is soft-deleted, or is disabled."""
    from server.database.relational_db.models.cognition_fabric_node import CognitionFabricNode

    cfn = (
        session.query(CognitionFabricNode)
        .filter(
            CognitionFabricNode.id == cfn_id,
            CognitionFabricNode.deleted_at.is_(None),
            CognitionFabricNode.enabled.is_(True),
        )
        .first()
    )
    if not cfn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cognition Fabric Node '{cfn_id}' not found or inactive",
        )


def _to_detail(engine: CognitionEngineModel) -> CognitionEngineDetail:
    return CognitionEngineDetail(
        id=engine.id,
        cfn_id=engine.cfn_id,
        name=engine.name,
        version=engine.version,
        kind=engine.kind,
        subkind=engine.subkind,
        url=engine.url,
        enabled=engine.enabled,
        mas_auto_associate=engine.mas_auto_associate,
        capabilities=engine.capabilities,
        metrics=engine.metrics,
        status=engine.status,
        last_seen=engine.last_seen,
        config=engine.config,
        mas_config=engine.mas_config,
        created_at=engine.created_at,
        updated_at=engine.updated_at,
    )


def _auth_for_storage(auth: Optional[dict]) -> Optional[dict]:
    """Encrypt credentials inside an auth dict before DB storage."""
    if not auth:
        return auth
    return process_config_for_storage({"auth": copy.deepcopy(auth)}).get("auth")


# Singleton instance
cognition_engine_service = CognitionEngineService()
