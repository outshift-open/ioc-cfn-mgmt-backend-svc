# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Memory Provider database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class MemoryProvider(Base):
    """Memory Provider model - represents a memory/graph database provider (shared across workspaces)"""

    __tablename__ = "memory_provider"

    memory_provider_id = Column(String(255), primary_key=True, nullable=False)
    memory_provider_name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    config = Column(JSONB, nullable=True)  # Provider-specific configuration
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    created_by = Column(String(36), nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return f"<MemoryProvider(memory_provider_id={self.memory_provider_id}, " f"name={self.memory_provider_name})>"
