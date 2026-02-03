"""Diagnostic API endpoints for IOC Management Backend standard diagnostics."""

import datetime
import os

from fastapi import Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from app_logging import get_loggers_info, update_log_level
from server.common import app, service_name
from server.health_check import HealthState, check_self


# Prometheus metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics_endpoint():
    """Prometheus metrics endpoint.

    Returns:
        Prometheus metrics in text format
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Pydantic models for request/response validation
class LogLevelUpdate(BaseModel):
    """Model for updating log level."""

    module_name: str
    log_level: str


################################################
# IOC Management Backend Standard Diagnostic API Endpoints
################################################
@app.get("/api/internal/diagnostics/health")
async def ioc_health():
    """IOC standard health endpoint for liveness probe.
    Returns a simple status for k8s liveness probe and also includes
    detailed service state information.

    Returns:
        JSONResponse with health status and 200/500 status code
    """
    service_state = check_self()
    timestamp = datetime.datetime.now().isoformat()

    # Construct response with both simple status and detailed info
    status = "UP" if service_state in [HealthState.UP, HealthState.DEGRADED] else "DOWN"
    response_body = {
        "status": status,
        "service_name": service_name,
        "service_state": service_state.name,
        "last_updated": timestamp,
    }

    # Return appropriate status code for k8s liveness probe
    if service_state in [HealthState.UP, HealthState.DEGRADED]:
        return JSONResponse(content=response_body, status_code=200)
    else:
        return JSONResponse(content=response_body, status_code=500)


@app.get("/api/internal/diagnostics/info")
async def ioc_info():
    """IOC Management Backend standard info endpoint with git commit information.

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


@app.get("/api/internal/diagnostics/metrics", include_in_schema=False)
async def metrics_endpoint():
    """Application metrics endpoint.

    Returns:
        Application metrics in JSON format
    """
    return {
        "uptime": os.environ.get("MOCK_APP_UPTIME", "unknown"),
        "requests_handled": os.environ.get("MOCK_REQUESTS_HANDLED", "unknown"),
    }


@app.get("/api/internal/diagnostics/loggers")
async def get_loggers():
    """Get current log level configuration.

    Returns:
        Dictionary with logger information
    """
    return get_loggers_info()


@app.post(
    "/api/internal/diagnostics/loggers",
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


@app.get("/healthz")
def healthz():
    service_state = check_self()

    timestamp = datetime.now().isoformat()
    response_body = {
        "service_name": service_name,
        "service_state": service_state.name,
        "last_updated": timestamp,
    }

    # Return appropriate status code for k8s liveness probe
    if service_state == HealthState.UP or service_state == HealthState.DEGRADED:
        return JSONResponse(content=response_body, status_code=200)
    else:
        return JSONResponse(content=response_body, status_code=500)
