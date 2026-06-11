# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import time

import requests

CFN_SVC_URL_DEFAULT = "http://localhost:9002"
CFN_SVC_MAS_METRICS_PATH = "/api/internal/mgmt/workspaces/{workspace_id}/multi-agentic-systems/{mas_id}/metrics"
CFN_SVC_TIMEOUT_SECONDS = 30
CFN_SVC_MAX_RETRIES = 3
CFN_SVC_RETRY_DELAY_SECONDS = 1


class CfnUpstreamError(Exception):
    """Raised when cfn-svc returns a client error that should be passed through."""

    def __init__(self, status_code: int, detail: dict):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"cfn-svc returned {status_code}")


class MASMetricsCfnService:
    """Service for fetching MAS metrics via HTTP calls to ioc-cfn-svc."""

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

    def fetch_mas_metrics(
        self,
        workspace_id: str,
        mas_id: str,
        start_time: str,
        end_time: str,
        ce_id: str = None,
        agent_id: str = None,
        metric_name: str = None,
    ) -> dict:
        """Fetch metrics for a MAS from cfn-svc.

        Args:
            workspace_id: The Workspace ID
            mas_id: The Multi-Agentic System ID
            start_time: Start of time range (Unix timestamp, RFC3339, or date)
            end_time: End of time range (Unix timestamp, RFC3339, or date)
            ce_id: Optional CE ID filter
            agent_id: Optional agent ID filter
            metric_name: Optional metric name filter (supports * wildcard)

        Returns:
            dict: Metrics response with series data
        """
        path = CFN_SVC_MAS_METRICS_PATH.format(workspace_id=workspace_id, mas_id=mas_id)
        url = f"{self._get_base_url()}{path}"

        params = {"start_time": start_time, "end_time": end_time}
        if ce_id:
            params["ce_id"] = ce_id
        if agent_id:
            params["agent_id"] = agent_id
        if metric_name:
            params["metric_name"] = metric_name

        self.logger.debug(f"Fetching MAS metrics from cfn-svc: {url}")
        try:
            response = self._get_with_retries(url, params=params)
            if response.status_code == 400:
                raise CfnUpstreamError(400, response.json())
            if response.status_code == 404:
                raise CfnUpstreamError(404, response.json())
            if response.status_code == 413:
                raise CfnUpstreamError(413, response.json())
            response.raise_for_status()
            return response.json()
        except CfnUpstreamError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch metrics for mas_id={mas_id}: {str(e)}")
            raise


# Global service instance
mas_metrics_cfn_service = MASMetricsCfnService()
