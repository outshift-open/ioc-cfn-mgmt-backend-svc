# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""MAS metrics API endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.services.mas_metrics_cfn import CfnUpstreamError, mas_metrics_cfn_service

router = APIRouter()


def _parse_timestamp(value: str) -> Optional[datetime]:
    """Parse a Unix timestamp, RFC3339 datetime, or YYYY-MM-DD date string into a datetime.

    Returns None if the value cannot be parsed in any supported format.
    """
    # Unix timestamp (integer or float)
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except ValueError:
        pass
    # RFC3339 / ISO 8601 datetime (Python <3.11 does not accept trailing Z natively)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    # Date only: YYYY-MM-DD
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return None


@router.get(
    "",
    status_code=200,
    summary="Query MAS metrics",
    description=(
        "Returns metrics for a Multi-Agentic System across all attached Cognition Engines. "
        "Optionally filter by CE, agent, or metric name."
    ),
    responses={
        200: {"description": "Metrics returned successfully"},
        400: {"description": "Invalid request parameters"},
        413: {"description": "Too many datapoints — narrow time range or add filters"},
        500: {"description": "Internal server error"},
    },
)
def fetch_mas_metrics(
    workspaceId: str,
    masId: str,
    start_time: str,
    end_time: str,
    ce_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    metric_name: Optional[str] = None,
):
    """
    Fetch metrics for a MAS.

    - **workspaceId**: The Workspace ID (from path)
    - **masId**: The Multi-Agentic System ID (from path)
    - **start_time**: Start of time range (Unix timestamp, RFC3339, or date e.g. 2026-06-01)
    - **end_time**: End of time range (Unix timestamp, RFC3339, or date)
    - **ce_id**: Optional — filter to metrics from a specific Cognition Engine
    - **agent_id**: Optional — filter to metrics from a specific agent
    - **metric_name**: Optional — filter by metric name (supports * wildcard)
    """
    try:
        uuid.UUID(workspaceId)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": f"invalid workspaceId: {workspaceId!r}"})
    try:
        uuid.UUID(masId)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": f"invalid masId: {masId!r}"})
    parsed_start = _parse_timestamp(start_time)
    if parsed_start is None:
        return JSONResponse(status_code=400, content={"error": f"invalid start_time: {start_time!r} — expected Unix timestamp, RFC3339, or YYYY-MM-DD"})
    parsed_end = _parse_timestamp(end_time)
    if parsed_end is None:
        return JSONResponse(status_code=400, content={"error": f"invalid end_time: {end_time!r} — expected Unix timestamp, RFC3339, or YYYY-MM-DD"})
    if parsed_start >= parsed_end:
        return JSONResponse(status_code=400, content={"error": "start_time must be before end_time"})

    try:
        result = mas_metrics_cfn_service.fetch_mas_metrics(
            workspace_id=workspaceId,
            mas_id=masId,
            start_time=start_time,
            end_time=end_time,
            ce_id=ce_id,
            agent_id=agent_id,
            metric_name=metric_name,
        )
        return JSONResponse(content=result)
    except CfnUpstreamError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"failed to fetch MAS metrics: {str(e)}"})
