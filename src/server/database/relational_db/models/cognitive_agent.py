# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognitive Agent database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class CognitiveAgent(Base):
    """Cognitive Agent model - represents a cognitive agent in a workspace"""

    __tablename__ = "cognitive_agent"

    cognitive_agent_id = Column(String(255), primary_key=True, nullable=False)
    workspace_id = Column(String(36), nullable=False, index=True)
    cognitive_agent_name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    config = Column(JSONB, nullable=True)  # Agent-specific configuration
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    created_by = Column(String(36), nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return (
            f"<CognitiveAgent(cognitive_agent_id={self.cognitive_agent_id}, "
            f"workspace_id={self.workspace_id}, name={self.cognitive_agent_name})>"
        )
