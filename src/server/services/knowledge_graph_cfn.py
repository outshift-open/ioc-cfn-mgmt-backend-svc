# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import time

import requests

CFN_SVC_URL_DEFAULT = "http://localhost:9002"
CFN_SVC_KNOWLEDGE_GRAPH_PATH = (
    "/api/internal/mgmt/workspaces/{workspace_id}/multi-agentic-systems/{mas_id}/knowledge-graph"
)
CFN_SVC_TIMEOUT_SECONDS = 10
CFN_SVC_MAX_RETRIES = 3
CFN_SVC_RETRY_DELAY_SECONDS = 1


class CfnUpstreamError(Exception):
    """Raised when cfn-svc returns a client error that should be passed through."""

    def __init__(self, status_code: int, detail: dict):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"cfn-svc returned {status_code}")


class KnowledgeGraphCfnService:
    """Service for fetching knowledge graph data via HTTP calls to ioc-cfn-svc."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_base_url(self) -> str:
        return os.getenv("CFN_SVC_URL", CFN_SVC_URL_DEFAULT)

    def _get_with_retries(self, url: str, params: dict = None) -> requests.Response:
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

    def fetch_knowledge_graph(self, workspace_id: str, mas_id: str) -> dict:
        """Fetch all nodes and edges for the given MAS from cfn-svc.

        Args:
            workspace_id: The Workspace ID
            mas_id: The Multi-Agentic System ID

        Returns:
            dict: Knowledge graph data with 'nodes' and 'relations'
        """
        path = CFN_SVC_KNOWLEDGE_GRAPH_PATH.format(workspace_id=workspace_id, mas_id=mas_id)
        url = f"{self._get_base_url()}{path}"

        self.logger.debug(f"Fetching knowledge graph from cfn-svc: {url}")
        try:
            response = self._get_with_retries(url)
            if response.status_code == 400:
                raise CfnUpstreamError(400, response.json())
            if response.status_code == 404:
                raise CfnUpstreamError(404, response.json())
            response.raise_for_status()
            return response.json()
        except CfnUpstreamError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch knowledge graph for mas_id={mas_id}: {str(e)}")
            raise


# Global service instance
knowledge_graph_cfn_service = KnowledgeGraphCfnService()
