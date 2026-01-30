from sqlalchemy import Column, String, DateTime, text, Index, UniqueConstraint

from server.database.relational_db.models import Base


class ApiKey(Base):
    __tablename__ = "api_key"

    id = Column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))

    # User ID - links API key to a user (single source of truth for permissions)
    user_id = Column(String(36), nullable=False)

    # Required fields
    key_hash = Column(String(256), nullable=False)  # Store hashed key using SHA-256
    key_preview = Column(String(20), nullable=False)  # First few chars for display (e.g., "tkf_abc123...")
    name = Column(String(200), nullable=False)  # Human-readable name for the key

    # Timestamp fields - auto-generated in database
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Soft delete field
    deleted_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_api_key_user_id", "user_id"),
        Index("idx_api_key_deleted_at", "deleted_at"),
        Index("idx_api_key_key_hash", "key_hash"),
        # Unique constraint: one user cannot have multiple API keys with the same name (excluding soft-deleted)
        Index(
            "idx_api_key_user_name_unique",
            "user_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self):
        return (
            f"<ApiKey(id='{self.id}', name='{self.name}', key_preview='{self.key_preview}', user_id='{self.user_id}')>"
        )
