import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import Field
from server.database.relational_db.models.audit import Audit
from server.database.relational_db.db import RelationalDB
from enum import Enum
from pydantic import BaseModel


class ResourceType(str, Enum):
    """Enum for different resource types in the system."""

    WORKSPACE = "WORKSPACE"
    USER = "USER"
    API_KEY = "API_KEY"
    MAS = "MAS"
    EXTERNAL_KNOWLEDGE = "EXTERNAL_KNOWLEDGE"
    SHARED_KNOWLEDGE = "SHARED_KNOWLEDGE"
    WORKSPACE_INVITATION = "WORKSPACE_INVITATION"
    WORKSPACE_MEMBER = "WORKSPACE_MEMBER"


class AuditEventType(str, Enum):
    """Enum for different audit event types."""

    RESOURCE_CREATED = "RESOURCE_CREATED"
    RESOURCE_UPDATED = "RESOURCE_UPDATED"
    RESOURCE_DELETED = "RESOURCE_DELETED"
    RESOURCE_PURGED = "RESOURCE_PURGED"
    RESOURCE_PRUNED = "RESOURCE_PRUNED"
    KNOWLEDGE_INGESTION = "KNOWLEDGE_INGESTION"
    REASONING_QUERY = "REASONING_QUERY"
    REASONING_FEEDBACK = "REASONING_FEEDBACK"
    INVITATION_CREATED = "INVITATION_CREATED"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED"
    INVITATION_DECLINED = "INVITATION_DECLINED"
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    INVITATION_CANCELLED = "INVITATION_CANCELLED"
    MEMBER_ADDED = "MEMBER_ADDED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    MEMBER_ROLE_UPDATED = "MEMBER_ROLE_UPDATED"


class AuditRequest(BaseModel):
    request_id: Optional[str] = Field(
        default=None, description="Optional request identifier (maps to request_id in database)"
    )
    operation_id: Optional[str] = Field(
        default=None,
        description="Optional operation identifier (maps to request_id in database if request_id is not provided)",
    )
    resource_type: ResourceType = Field(..., description="Type of the resource being audited")
    audit_resource_id: str = Field(
        ..., description="UUID of the resource being audited (maps to audit_resource_id in database)"
    )
    audit_type: AuditEventType = Field(..., description="Type of audit action")
    audit_information: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON blob of the audit event details"
    )
    audit_extra_information: Optional[str] = Field(
        default=None, description="Additional information as a string (e.g., SUCCESS or error message)"
    )
    created_by: Optional[str] = Field(default=None, description="UUID of the API Key or user who created the audit")
    updated_by: Optional[str] = Field(default=None, description="UUID of the API Key or user who updated the audit")
    deleted_by: Optional[str] = Field(default=None, description="UUID of the API Key or user who deleted the audit")
    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the audit was created (auto-generated if not provided)"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the audit was last updated (auto-generated if not provided)"
    )
    deleted_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the audit was deleted (auto-generated if not provided)"
    )


class AuditService:
    def __init__(self):
        # Get logger instance (logging is setup in main.py)
        self.logger = logging.getLogger(__name__)

    def create_audit(self, audit: AuditRequest) -> Audit:
        """Create a new audit entry.

        Args:
            audit: AuditRequest object containing audit details

        Returns:
            Audit: The created audit record
        """
        db = RelationalDB()
        session = db.get_session()
        self.logger.debug(f"Creating audit entry: {audit}")
        try:
            audit_entry = Audit(
                request_id=audit.request_id or audit.operation_id,
                resource_type=audit.resource_type,
                audit_type=audit.audit_type,
                audit_resource_id=audit.audit_resource_id,
                audit_information=audit.audit_information if audit.audit_information else None,
                audit_extra_information=audit.audit_extra_information,
                created_by=audit.created_by,
                updated_by=audit.updated_by,
                deleted_by=audit.deleted_by,
                created_at=audit.created_at,
                updated_at=audit.updated_at,
                deleted_at=audit.deleted_at,
            )
            session.add(audit_entry)
            session.commit()
            self.logger.debug(f"Successfully created audit entry: {audit_entry}")
            return audit_entry
        except Exception as e:
            self.logger.error(f"Failed to create audit entry: {str(e)}")
            session.rollback()
            raise e
        finally:
            session.close()

    def get_audit(self, audit_id: str) -> Optional[Audit]:
        """Retrieve a specific audit entry by ID.

        Args:
            audit_id: The ID of the audit to retrieve

        Returns:
            Audit: The audit record if found, None otherwise
        """
        db = RelationalDB()
        session = db.get_session()
        self.logger.debug(f"Retrieving audit: {audit_id}")
        try:
            audit_entry: Optional[Audit] = (
                session.query(Audit).filter(Audit.id == audit_id, Audit.deleted_at.is_(None)).first()
            )
            self.logger.debug(f"Successfully retrieved audit: {audit_entry}")
            return audit_entry
        except Exception as e:
            self.logger.error(f"Failed to retrieve audit: {str(e)}")
            raise e
        finally:
            session.close()

    def list_audits(self, skip: int = 0, limit: int = 100) -> tuple[list[Audit], int]:
        """List all audit entries with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            tuple: (list of audit records, total count)
        """
        db = RelationalDB()
        session = db.get_session()
        self.logger.debug(f"Listing audits with skip={skip}, limit={limit}")
        try:
            total: int = session.query(Audit).filter(Audit.deleted_at.is_(None)).count()
            audits: list[Audit] = (
                session.query(Audit)
                .filter(Audit.deleted_at.is_(None))
                .order_by(Audit.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            self.logger.debug(f"Successfully listed {len(audits)} audits")
            return audits, total
        except Exception as e:
            self.logger.error(f"Failed to list audits: {str(e)}")
            raise e
        finally:
            session.close()

    def delete_audit(self, audit_id: str) -> bool:
        """Soft delete an audit entry by ID.

        Args:
            audit_id: The ID of the audit to delete

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        db = RelationalDB()
        session = db.get_session()
        self.logger.debug(f"Deleting audit: {audit_id}")
        try:
            audit_entry: Optional[Audit] = (
                session.query(Audit).filter(Audit.id == audit_id, Audit.deleted_at.is_(None)).first()
            )
            if not audit_entry:
                self.logger.warning(f"Audit not found: {audit_id}")
                return False

            audit_entry.deleted_at = datetime.now()  # type: ignore[assignment]
            session.commit()
            self.logger.debug(f"Successfully deleted audit: {audit_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete audit: {str(e)}")
            session.rollback()
            raise e
        finally:
            session.close()


# Global service instance
audit_service = AuditService()
