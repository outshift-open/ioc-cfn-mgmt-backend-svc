# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class CognitionEngine(Base):
    """Cognition Engine model - CFN-scoped cognition processing engine"""

    __tablename__ = "cognition_engine"

    id = Column(String(255), primary_key=True, nullable=False)
    cfn_id = Column(String(255), ForeignKey("cognition_fabric_node.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Connection info
    url = Column(String(512), nullable=False)

    # Authentication (optional - credentials for CFN to reach CE, encrypted)
    auth = Column(JSONB, nullable=True)

    # Type and capabilities
    # kinds_subkinds: dict mapping kind -> list of subkinds
    # e.g. {"intent": ["mission"], "exchange": ["team-formation"]}
    kinds_subkinds = Column(JSONB, nullable=True, default=dict)
    subprotocols = Column(JSONB, nullable=True, default=list)
    # category: CE category - 'UNKNOWN', 'GAT' (Gateway), or 'COG' (Cognition, default)
    category = Column(String(20), nullable=False, default="COG")
    capabilities = Column(JSONB, nullable=True, default=list)
    metrics = Column(JSONB, nullable=True, default=list)

    # Versioning
    version = Column(String(50), nullable=False)

    # Lifecycle
    enabled = Column(Boolean, nullable=False, default=True)
    mas_auto_associate = Column(Boolean, nullable=False, default=False)

    # Status
    status = Column(String(20), nullable=False, default="offline")
    last_seen = Column(TIMESTAMP(timezone=True), nullable=True)

    # Configuration
    config = Column(JSONB, nullable=True, default=dict)
    mas_config = Column(JSONB, nullable=True, default=dict)

    # Audit fields
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, onupdate=func.now())
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    def __repr__(self):
        return f"<CognitionEngine(id={self.id}, cfn_id={self.cfn_id}, name={self.name})>"
