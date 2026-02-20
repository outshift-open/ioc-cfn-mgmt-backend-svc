"""Policy database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class Policy(Base):
    """Policy model - represents a policy configuration"""

    __tablename__ = "policy"

    policy_id = Column(String(255), primary_key=True, nullable=False)
    workspace_id = Column(String(36), nullable=False, index=True)
    policy_name = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=True)  # Policy-specific configuration
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    created_by = Column(String(36), nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return f"<Policy(policy_id={self.policy_id}, workspace_id={self.workspace_id}, name={self.policy_name})>"
