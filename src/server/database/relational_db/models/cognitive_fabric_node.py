from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB

from server.database.relational_db.models import Base


class CognitiveFabricNode(Base):
    __tablename__ = "cognitive_fabric_node"

    # Primary key - CFN's persistent ID (not auto-generated)
    cfn_id = Column(String(255), primary_key=True, nullable=False)

    # Required fields
    workspace_id = Column(String(36), ForeignKey("workspace.id"), nullable=False)
    cfn_name = Column(String(255), nullable=False)

    # Optional fields
    cfn_config = Column(JSONB, nullable=True)
    cloud_config = Column(JSONB, nullable=True)

    # Status tracking
    status = Column(String(50), nullable=False, server_default=text("'online'"))
    last_seen = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    enabled = Column(Boolean, nullable=False, server_default="true")

    # Timestamp fields
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
        Index("idx_cfn_workspace_id", "workspace_id"),
        Index("idx_cfn_status", "status"),
        Index("idx_cfn_last_seen", "last_seen"),
        Index("idx_cfn_deleted_at", "deleted_at"),
        Index("idx_cfn_enabled", "enabled"),
        # Enforce unique CFN names within a workspace (excluding soft-deleted)
        Index(
            "idx_cfn_workspace_name_unique",
            "workspace_id",
            "cfn_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self):
        return (
            f"<CognitiveFabricNode(cfn_id='{self.cfn_id}', cfn_name='{self.cfn_name}', "
            f"workspace_id='{self.workspace_id}', status='{self.status}')>"
        )
