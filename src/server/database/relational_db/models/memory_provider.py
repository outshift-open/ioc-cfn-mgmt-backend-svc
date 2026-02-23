"""Memory Provider database model"""

from datetime import datetime, timezone

from sqlalchemy import TIMESTAMP, Boolean, Column, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class MemoryProvider(Base):
    """Memory Provider model - represents a memory/graph database provider (shared across workspaces)"""

    __tablename__ = "memory_provider"

    memory_provider_id = Column(String(255), primary_key=True, nullable=False)
    memory_provider_name = Column(String(255), nullable=False)
    provider_type = Column(String(50), nullable=False)  # vector_store, graph_db, etc.
    provider = Column(String(100), nullable=False)  # ioc-memory-provider
    config = Column(JSONB, nullable=True)  # Provider-specific configuration
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    created_by = Column(String(36), nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self):
        return f"<MemoryProvider(memory_provider_id={self.memory_provider_id}, " f"name={self.memory_provider_name})>"


class WorkspaceMemoryProvider(Base):
    """Many-to-many association between workspaces and memory providers"""

    __tablename__ = "workspace_memory_provider"

    workspace_id = Column(
        String(36),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    memory_provider_id = Column(
        String(255),
        ForeignKey("memory_provider.memory_provider_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    created_by = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_wmp_workspace_id", "workspace_id"),
        Index("idx_wmp_memory_provider_id", "memory_provider_id"),
    )

    def __repr__(self):
        return (
            f"<WorkspaceMemoryProvider(workspace_id='{self.workspace_id}', "
            f"memory_provider_id='{self.memory_provider_id}')>"
        )
