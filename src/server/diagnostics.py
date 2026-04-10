# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Diagnostic API endpoints for IoC Management Backend standard diagnostics."""

import datetime
import os

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import REGISTRY
from pydantic import BaseModel, ConfigDict, Field

from app_logging import get_loggers_info, update_log_level
from server.common import service_name
from server.health_check import HealthState, check_self

router = APIRouter()


class LogLevelUpdate(BaseModel):
    """Model for updating log level."""

    model_config = ConfigDict(populate_by_name=True)

    module_name: str = Field(alias="module-name")
    log_level: str = Field(alias="log-level")


@router.get("/health")
async def ioc_health():
    """IoC standard health endpoint for liveness probe.
    Returns a simple status for k8s liveness probe and also includes
    detailed service state information.

    Returns:
        JSONResponse with health status and 200/500 status code
    """
    service_state = check_self()
    timestamp = datetime.datetime.now().isoformat()

    status_str = "UP" if service_state in [HealthState.UP, HealthState.DEGRADED] else "DOWN"
    response_body = {
        "status": status_str,
        "service_name": service_name,
        "service_state": service_state.name,
        "last_updated": timestamp,
    }

    if service_state in [HealthState.UP, HealthState.DEGRADED]:
        return JSONResponse(content=response_body, status_code=200)
    else:
        return JSONResponse(content=response_body, status_code=500)


@router.get("/info")
async def ioc_info():
    """IoC Management Backend standard info endpoint with git commit information.

    Returns:
        Dictionary with git commit information
    """
    return {
        "git": {
            "commit": {
                "time": os.environ.get("GIT_COMMIT_TIME", "unknown"),
                "id": os.environ.get("GIT_COMMIT_SHA", "unknown"),
            },
            "branch": os.environ.get("GIT_BRANCH", "main"),
        }
    }


@router.get("/metrics")
async def list_metrics():
    """List all metrics published by this service.

    Returns:
        List of metric descriptors from the Prometheus registry
    """
    metrics = []
    for metric in REGISTRY.collect():
        metrics.append(
            {
                "name": metric.name,
                "type": metric.type,
                "help": metric.documentation,
            }
        )
    return {"metrics": metrics}


@router.get("/metrics/{metric_name}")
async def get_metric(metric_name: str):
    """Get current value of a specific metric by name.

    Args:
        metric_name: Prometheus metric name

    Returns:
        Metric descriptor with current sample values, or 404 if not found
    """
    for metric in REGISTRY.collect():
        if metric.name == metric_name:
            return {
                "name": metric.name,
                "type": metric.type,
                "help": metric.documentation,
                "samples": [
                    {
                        "name": sample.name,
                        "labels": dict(sample.labels),
                        "value": sample.value,
                    }
                    for sample in metric.samples
                ],
            }
    return JSONResponse(
        content={"error": f"Metric '{metric_name}' not found"},
        status_code=404,
    )


@router.get("/loggers")
async def get_loggers():
    """Get current log level configuration.

    Returns:
        Dictionary with logger information
    """
    return get_loggers_info()


@router.put(
    "/loggers",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_loggers(log_config: LogLevelUpdate):
    """Update log level for a specific module or root logger.

    Args:
        log_config: Log level update configuration

    Returns:
        204 on success, 400 with error message on failure
    """
    success, error_msg = update_log_level(log_config.module_name, log_config.log_level)

    if not success:
        return JSONResponse(content={"error": error_msg}, status_code=400)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
