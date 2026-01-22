from sqlalchemy import Column, String, DateTime, text, Index, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY

from server.database.relational_db.models import Base


class ApiKey(Base):
    __tablename__ = "api_key"

    id = Column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))

    # Foreign key to workspace
    workspace_id = Column(String(36), ForeignKey("workspace.id"), nullable=True)

    # Required fields
    key_hash = Column(String(256), nullable=False)  # Store hashed key using bcrypt
    key_preview = Column(String(20), nullable=False)  # First few chars for display (e.g., "tkf_abc123...")
    name = Column(String(200), nullable=False)  # Human-readable name for the key
    roles = Column(ARRAY(String), nullable=False)  # Array of role strings (e.g., ["admin", "viewer"])

    # Timestamp fields - auto-generated in database
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Soft delete field
    deleted_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_api_key_workspace_id", "workspace_id"),
        Index("idx_api_key_deleted_at", "deleted_at"),
        Index("idx_api_key_key_hash", "key_hash"),
    )

    def __repr__(self):
        return f"<ApiKey(id='{self.id}', name='{self.name}', key_preview='{self.key_preview}')>"
