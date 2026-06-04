# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""MAS ↔ CE junction table model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class MasCognitionEngine(Base):
    """Many-to-many association between MultiAgenticSystem and CognitionEngine."""

    __tablename__ = "mas_cognition_engines"

    mas_id = Column(
        String(36),
        ForeignKey("multi_agentic_system.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    ce_id = Column(
        String(255),
        ForeignKey("cognition_engine.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    mas_config = Column(JSONB, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by = Column(String(255), nullable=True)

    __table_args__ = (Index("idx_mas_ce_ce_id", "ce_id"),)

    def __repr__(self):
        return f"<MasCognitionEngine(mas_id='{self.mas_id}', ce_id='{self.ce_id}')>"
