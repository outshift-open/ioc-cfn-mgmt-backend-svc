import logging
from typing import Optional

from server.database.relational_db.cfn_cp_db import CfnCpDB
from server.database.relational_db.models.cfn_audit import CfnAudit


class AuditCfnEventService:
    """Service for querying CFN audit events from the cfn_cp database."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_audit_event(self, audit_event_id: str) -> Optional[CfnAudit]:
        """Retrieve a specific audit event by ID.

        Args:
            audit_event_id: The UUID of the audit event to retrieve

        Returns:
            CfnAudit: The audit event record if found, None otherwise
        """
        db = CfnCpDB()
        session = db.get_session()
        self.logger.debug(f"Retrieving audit event: {audit_event_id}")
        try:
            audit_event: Optional[CfnAudit] = (
                session.query(CfnAudit).filter(CfnAudit.id == audit_event_id).first()
            )
            self.logger.debug(f"Successfully retrieved audit event: {audit_event}")
            return audit_event
        except Exception as e:
            self.logger.error(f"Failed to retrieve audit event: {str(e)}")
            raise e
        finally:
            session.close()

    def list_audit_events(
        self,
        skip: int = 0,
        limit: int = 100,
        resource_type: Optional[str] = None,
        audit_type: Optional[str] = None,
    ) -> tuple[list[CfnAudit], int]:
        """List audit events with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            resource_type: Optional filter by resource_type (e.g. MAS, WORKSPACE)
            audit_type: Optional filter by audit_type (e.g. RESOURCE_CREATED)

        Returns:
            tuple: (list of audit event records, total count)
        """
        db = CfnCpDB()
        session = db.get_session()
        self.logger.debug(
            f"Listing audit events with skip={skip}, limit={limit}, "
            f"resource_type={resource_type}, audit_type={audit_type}"
        )
        try:
            query = session.query(CfnAudit)

            if resource_type:
                query = query.filter(CfnAudit.resource_type == resource_type)
            if audit_type:
                query = query.filter(CfnAudit.audit_type == audit_type)

            total: int = query.count()
            audit_events: list[CfnAudit] = (
                query.order_by(CfnAudit.created_on.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            self.logger.debug(f"Successfully listed {len(audit_events)} audit events")
            return audit_events, total
        except Exception as e:
            self.logger.error(f"Failed to list audit events: {str(e)}")
            raise e
        finally:
            session.close()


# Global service instance
audit_cfn_event_service = AuditCfnEventService()
