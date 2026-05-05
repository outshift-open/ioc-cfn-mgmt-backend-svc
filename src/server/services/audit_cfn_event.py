# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import time
from typing import Optional

import requests

CFN_SVC_URL_DEFAULT = "http://localhost:9002"
CFN_SVC_AUDIT_PATH = "/api/internal/mgmt/audit"
CFN_SVC_TIMEOUT_SECONDS = 10
CFN_SVC_MAX_RETRIES = 3
CFN_SVC_RETRY_DELAY_SECONDS = 1


class CfnUpstreamError(Exception):
    """Raised when cfn-svc returns a client error (e.g. 400) that should be passed through."""

    def __init__(self, status_code: int, detail: dict):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"cfn-svc returned {status_code}")


FALLBACK_DEFAULT_PAGE_SIZE = 20
FALLBACK_MAX_PAGE_SIZE = 100


def _get_default_page_size() -> int:
    """Return DEFAULT_PAGE_SIZE from env, falling back to 20."""
    try:
        val = int(os.getenv("DEFAULT_PAGE_SIZE", str(FALLBACK_DEFAULT_PAGE_SIZE)))
        return val if val > 0 else FALLBACK_DEFAULT_PAGE_SIZE
    except (ValueError, TypeError):
        return FALLBACK_DEFAULT_PAGE_SIZE


def _get_max_page_size() -> int:
    """Return MAX_PAGE_SIZE from env, falling back to 100."""
    try:
        val = int(os.getenv("MAX_PAGE_SIZE", str(FALLBACK_MAX_PAGE_SIZE)))
        return val if val > 0 else FALLBACK_MAX_PAGE_SIZE
    except (ValueError, TypeError):
        return FALLBACK_MAX_PAGE_SIZE


class AuditCfnEventService:
    """Service for querying CFN audit events via HTTP calls to ioc-cfn-svc."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_base_url(self) -> str:
        """Get the cfn-svc base URL from environment."""
        return os.getenv("CFN_SVC_URL", CFN_SVC_URL_DEFAULT)

    def _get_with_retries(self, url: str, params: dict = None) -> requests.Response:
        """GET with simple retry logic."""
        last_error = None
        for attempt in range(1, CFN_SVC_MAX_RETRIES + 1):
            try:
                response = requests.get(url, params=params, timeout=CFN_SVC_TIMEOUT_SECONDS)
                return response
            except requests.exceptions.RequestException as e:
                last_error = e
                self.logger.warning(f"cfn-svc request failed (attempt {attempt}/{CFN_SVC_MAX_RETRIES}): {str(e)}")
                if attempt < CFN_SVC_MAX_RETRIES:
                    time.sleep(CFN_SVC_RETRY_DELAY_SECONDS * attempt)
        raise last_error

    def get_audit_event(self, audit_event_id: str) -> Optional[dict]:
        """Retrieve a specific audit event by ID via cfn-svc HTTP API.

        Args:
            audit_event_id: The UUID of the audit event to retrieve

        Returns:
            dict: The audit event data if found, None otherwise
        """
        url = f"{self._get_base_url()}{CFN_SVC_AUDIT_PATH}/{audit_event_id}"
        self.logger.debug(f"Retrieving audit event from cfn-svc: {url}")
        try:
            response = self._get_with_retries(url)
            if response.status_code == 404:
                return None
            if response.status_code == 400:
                raise CfnUpstreamError(400, response.json())
            response.raise_for_status()
            return response.json()
        except CfnUpstreamError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve audit event {audit_event_id} from cfn-svc: {str(e)}")
            raise

    def list_audit_events(
        self,
        page: int = 0,
        page_size: int = None,
        resource_type: Optional[str] = None,
        audit_type: Optional[str] = None,
    ) -> dict:
        """List audit events via cfn-svc HTTP API with optional filtering and pagination.

        Args:
            page: 0-based page number (default 0)
            page_size: Number of records per page (default from DEFAULT_PAGE_SIZE env, clamped to MAX_PAGE_SIZE)
            resource_type: Optional filter by resource_type (e.g. MAS, WORKSPACE)
            audit_type: Optional filter by audit_type (e.g. RESOURCE_CREATED)

        Returns:
            dict: Response containing 'data' (list of audit events) and 'pageInfo'
        """
        if page_size is None or page_size <= 0:
            page_size = _get_default_page_size()
        max_ps = _get_max_page_size()
        if page_size > max_ps:
            page_size = max_ps

        url = f"{self._get_base_url()}{CFN_SVC_AUDIT_PATH}"
        params = {"page": page, "pageSize": page_size}
        if resource_type:
            params["resource_type"] = resource_type
        if audit_type:
            params["audit_type"] = audit_type

        self.logger.debug(f"Listing audit events from cfn-svc: {url} with params={params}")
        try:
            response = self._get_with_retries(url, params=params)
            if response.status_code == 400:
                raise CfnUpstreamError(400, response.json())
            response.raise_for_status()
            result = response.json()
            page_count = len(result.get("data", []))
            self.logger.debug(f"Successfully listed {page_count} audit events from cfn-svc")
            return result
        except CfnUpstreamError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to list audit events from cfn-svc: {str(e)}")
            raise


# Global service instance
audit_cfn_event_service = AuditCfnEventService()
