# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Policy database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class Policy(Base):
    """Policy model - represents a policy configuration"""

    __tablename__ = "policy"

    id = Column(String(36), primary_key=True, nullable=False)
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    created_by = Column(String(36), nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return f"<Policy(id={self.id}, workspace_id={self.workspace_id}, name={self.name})>"
