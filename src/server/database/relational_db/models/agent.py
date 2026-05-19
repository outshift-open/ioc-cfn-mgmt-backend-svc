# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Agent database model - dedicated table for MAS agents"""

from sqlalchemy import Column, String, DateTime, Text, text, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class Agent(Base):
    __tablename__ = "agent"

    agent_id = Column(String(255), primary_key=True)
    mas_id = Column(String(36), ForeignKey("multi_agentic_system.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=True)
    url = Column(Text, nullable=True)
    identity_type = Column(String(50), nullable=True)
    identity_identifiers = Column(JSONB, nullable=True)
    agentic_memory_provider_id = Column(
        String(255), ForeignKey("memory_provider.id", ondelete="SET NULL"), nullable=True
    )
    config = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_agent_mas_id", "mas_id"),
        Index("idx_agent_identity_type", "identity_type"),
        Index("idx_agent_agentic_memory", "agentic_memory_provider_id"),
        UniqueConstraint("mas_id", "name", name="uq_agent_mas_name"),
    )

    def __repr__(self):
        return f"<Agent(agent_id='{self.agent_id}', mas_id='{self.mas_id}')>"
