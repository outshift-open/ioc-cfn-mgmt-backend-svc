# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Engine database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class CognitionEngine(Base):
    """Cognition Engine model - represents a cognition processing engine"""

    __tablename__ = "cognition_engine"

    cognition_engine_id = Column(String(255), primary_key=True, nullable=False)
    workspace_id = Column(String(36), nullable=False, index=True)
    cognition_engine_name = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=True)  # Engine-specific configuration (host, port, etc.)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    created_by = Column(String(36), nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return (
            f"<CognitionEngine(cognition_engine_id={self.cognition_engine_id}, "
            f"workspace_id={self.workspace_id}, name={self.cognition_engine_name})>"
        )
