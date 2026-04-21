# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import time

import requests

CFN_SVC_URL_DEFAULT = "http://localhost:9002"
CFN_SVC_VECTOR_STORE_PATH = (
    "/api/internal/workspaces/{workspace_id}/multi-agentic-systems/{mas_id}/shared-memories/vector-store"
)
CFN_SVC_TIMEOUT_SECONDS = 10
CFN_SVC_MAX_RETRIES = 3
CFN_SVC_RETRY_DELAY_SECONDS = 1


class VectorStoreCfnService:
    """Service for onboarding and deleting per-MAS vector stores via HTTP calls to ioc-cfn-svc."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_base_url(self) -> str:
        return os.getenv("CFN_SVC_URL", CFN_SVC_URL_DEFAULT)

    def _post_with_retries(self, url: str) -> requests.Response:
        last_error = None
        for attempt in range(1, CFN_SVC_MAX_RETRIES + 1):
            try:
                response = requests.post(url, timeout=CFN_SVC_TIMEOUT_SECONDS)
                return response
            except requests.exceptions.RequestException as e:
                last_error = e
                self.logger.warning(
                    f"cfn-svc request to onboard vector store failed "
                    f"(attempt {attempt}/{CFN_SVC_MAX_RETRIES}): {str(e)}"
                )
                if attempt < CFN_SVC_MAX_RETRIES:
                    time.sleep(CFN_SVC_RETRY_DELAY_SECONDS * attempt)
        raise last_error

    def onboard_vector_store(self, workspace_id: str, mas_id: str) -> None:
        """Onboard the vector store for a newly created MAS.

        Calls CFN's POST vector-store endpoint to create the per-MAS vector table.
        Errors are logged but not re-raised so that MAS creation is never blocked.

        Args:
            workspace_id: The Workspace ID
            mas_id: The Multi-Agentic System ID
        """
        path = CFN_SVC_VECTOR_STORE_PATH.format(workspace_id=workspace_id, mas_id=mas_id)
        url = f"{self._get_base_url()}{path}"

        self.logger.info(f"Onboarding vector store via cfn-svc: {url}")
        try:
            response = self._post_with_retries(url)
            response.raise_for_status()
            self.logger.info(f"Vector store onboarded successfully | workspace={workspace_id} mas={mas_id}")
        except Exception as e:
            self.logger.warning(
                f"Failed to onboard vector store for mas_id={mas_id}: {str(e)} "
                "(MAS creation succeeded; vector store can be onboarded manually)"
            )


# Global service instance
vector_store_cfn_service = VectorStoreCfnService()
