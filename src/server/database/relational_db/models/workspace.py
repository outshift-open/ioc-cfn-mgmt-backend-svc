from sqlalchemy import Column, String, DateTime, text, Index
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from server.database.relational_db.models import Base


class Workspace(Base):
    __tablename__ = "workspace"

    id = Column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))

    # Required fields
    name = Column(String(255), nullable=False)

    # Optional fields
    users = Column(ARRAY(String), nullable=True)
    config = Column(JSONB, nullable=True)

    # Timestamp fields - auto-generated in database
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Soft delete field
    deleted_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_workspace_name", "name"),
        Index("idx_workspace_deleted_at", "deleted_at"),
    )

    def __repr__(self):
        return f"<Workspace(id='{self.id}', name='{self.name}')>"
