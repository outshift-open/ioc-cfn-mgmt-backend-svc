from sqlalchemy import Column, String, DateTime, Text, text, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class MultiAgenticSystem(Base):
    __tablename__ = "multi_agentic_system"

    id = Column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))

    # Required fields
    workspace_id = Column(String(36), ForeignKey("workspace.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Optional fields
    description = Column(Text, nullable=True)
    agents = Column(JSONB, nullable=True)
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
        Index("idx_mas_workspace_id", "workspace_id"),
        Index("idx_mas_deleted_at", "deleted_at"),
        # Enforce unique active MAS names within a workspace
        Index(
            "idx_mas_workspace_name_unique",
            "workspace_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self):
        return f"<MultiAgenticSystem(id='{self.id}', name='{self.name}', workspace_id='{self.workspace_id}')>"
