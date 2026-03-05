from sqlalchemy import Column, String, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from server.database.relational_db.models import Base


class CfnAudit(Base):
    """
    Model for the 'audits' table in the cfn_cp database.
    Maps to the Go Audit struct used by ioc-cfn-svc.
    """

    __tablename__ = "audits"

    # Primary key - UUID type matching gorm:"type:uuid;primaryKey"
    id = Column(UUID(as_uuid=True), primary_key=True)

    # Optional operation identifier - gorm:"size:128"
    operation_id = Column(String(128), nullable=True)

    # Required fields
    resource_type = Column(String(64), nullable=False)
    resource_identifier = Column(String(128), nullable=False)
    audit_type = Column(String(64), nullable=False)
    audit_resource_identifier = Column(String(128), nullable=False)

    # JSONB field - gorm:"type:jsonb"
    audit_information = Column(JSONB, nullable=True)

    # Optional extra info
    audit_extra_information = Column(Text, nullable=True)

    # Tracking fields - UUID types
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_on = Column(DateTime(timezone=True), nullable=False)
    last_modified_by = Column(UUID(as_uuid=True), nullable=False)
    last_modified_on = Column(DateTime(timezone=True), nullable=False)

    # Indexes for common query patterns
    __table_args__ = (
        Index("idx_cfn_audit_resource_type", "resource_type"),
        Index("idx_cfn_audit_audit_type", "audit_type"),
        Index("idx_cfn_audit_resource_identifier", "resource_identifier"),
        Index("idx_cfn_audit_created_on", "created_on"),
    )

    def __repr__(self):
        return (
            f"<CfnAudit(id='{self.id}', operation_id='{self.operation_id}', "
            f"resource_type='{self.resource_type}', audit_type='{self.audit_type}', "
            f"resource_identifier='{self.resource_identifier}', "
            f"audit_resource_identifier='{self.audit_resource_identifier}', "
            f"created_by='{self.created_by}', created_on='{self.created_on}')>"
        )
