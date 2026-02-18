"""Cognitive Agent database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class CognitiveAgent(Base):
    """Cognitive Agent model - built-in default agents/functions (global, read-only).

    These are associated with every MAS in every Workspace.
    No CUD operations — read only.
    """

    __tablename__ = "cognitive_agent"

    cognitive_agent_id = Column(String(255), primary_key=True, nullable=False)
    cognitive_agent_name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    config = Column(JSONB, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_ca_name_unique",
            "cognitive_agent_name",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<CognitiveAgent(cognitive_agent_id={self.cognitive_agent_id}, " f"name={self.cognitive_agent_name})>"
