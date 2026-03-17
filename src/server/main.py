# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app_logging.logger import setup_logging
from server.common import service_name
from server.utils.repo_root import REPO_ROOT

# Load environment variables first (before importing modules that read env vars)
load_dotenv(dotenv_path=REPO_ROOT + "/env.conf", override=True)  # Load from repo root

# Setup logging before importing application modules that instantiate singletons at import time
setup_logging(service_name)

from server.api.api import api_router  # noqa: E402
from server.database.relational_db.db import RelationalDB  # noqa: E402
from server.database.relational_db.cfn_cp_db import CfnCpDB  # noqa: E402
from server.services.cognition_fabric_node_monitor import cognitive_fabric_node_monitor  # noqa: E402
from server.services.user import UserService  # noqa: E402
from server.utils.version import get_app_version  # noqa: E402

logger = logging.getLogger(__name__)
logger.info("Environment variables loaded")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""

    # Database Setup
    try:
        db = RelationalDB()
        db.init()
    except Exception as e:
        logger.error(f"Relational Database initialization failed: {str(e)}")
        raise

    # CfnCp Database Setup (cfn_cp database for audit events)
    try:
        cfn_cp_db = CfnCpDB()
        cfn_cp_db.init()
    except Exception as e:
        logger.error(f"CfnCp Database initialization failed: {str(e)}")
        raise

    logger.info("Database connections initialized")

    # Create admin user if not exists
    try:
        from server.services.user import ADMIN_USER_ID_DEFAULT, ADMIN_WORKSPACE_ID_DEFAULT

        admin_response = UserService().create_admin_user()
    except Exception as e:
        logger.error(f"Admin user creation failed: {str(e)}")
        raise

    # Display admin API key if CFN_DEV_MODE is enabled
    cfn_dev_mode = os.getenv("CFN_DEV_MODE", "false").lower() == "true"
    if cfn_dev_mode:
        admin_api_key = admin_response.api_key
        logger.warning(
            "\n"
            + "=" * 80
            + "\n"
            + "CFN DEV MODE ENABLED - Hardcoded IDs for Testing\n"
            + "=" * 80
            + "\n"
            + f"Admin User ID:  {ADMIN_USER_ID_DEFAULT}\n"
            + f"Workspace ID:   {ADMIN_WORKSPACE_ID_DEFAULT}\n"
            + f"Admin API Key:  {admin_api_key}\n"
            + "\n"
            + "Example CFN Registration:\n"
            + "curl -X POST http://localhost:8000/api/cognition-fabric-nodes/register \\\n"
            + f'  -H "X-API-Key: {admin_api_key}" \\\n'
            + '  -H "Content-Type: application/json" \\\n'
            + '  -d \'{"cfn_id": "cfn-001", "cfn_name": "test-node", '
            + f'"workspace_id": "{ADMIN_WORKSPACE_ID_DEFAULT}"}}\'\n'
            + "\n"
            + "WARNING: This is for DEVELOPMENT/TESTING ONLY! Never use in production!\n"
            + "=" * 80
            + "\n"
        )

    # Start Cognitive Fabric Node monitor background task
    cognitive_fabric_node_monitor_task = asyncio.create_task(cognitive_fabric_node_monitor.start())
    logger.info("Cognitive Fabric Node monitor started")

    yield

    # Shutdown
    logger.info("Stopping Cognitive Fabric Node monitor...")
    cognitive_fabric_node_monitor.stop()
    try:
        await asyncio.wait_for(cognitive_fabric_node_monitor_task, timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Cognitive Fabric Node monitor task did not stop gracefully, cancelling...")
        cognitive_fabric_node_monitor_task.cancel()
    logger.info("Cognitive Fabric Node monitor stopped")

    logger.info("Closing database connections...")
    db.close()
    cfn_cp_db.close()
    # await graph_db.close()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title=f"{service_name} API",
    version=get_app_version(),
    description="IoC CFN Management Backend Service API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

instrumentator = Instrumentator()
instrumentator.instrument(app)
instrumentator.expose(app, endpoint="/metrics")


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/env")
def env_var():
    return {
        "service": service_name,
        "environment_variables": {
            "CONFIGMAP_TEST": os.environ.get("CONFIGMAP_TEST"),
            "CONFIGMAP_DEFAULT_EXAMPLE": os.environ.get("CONFIGMAP_DEFAULT_EXAMPLE"),
            "CONFIGMAP_OVERLAY_EXAMPLE": os.environ.get("CONFIGMAP_OVERLAY_EXAMPLE"),
            "APPLICATION_VERSION": os.environ.get("APPLICATION_VERSION"),
            "MOCK_DB_UPTIME": os.environ.get("MOCK_DB_UPTIME"),
            "MOCK_FOO_UPTIME": os.environ.get("MOCK_FOO_UPTIME"),
        },
    }


################################################
# Service-Specific API Endpoints
################################################
# Register API routes
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    log_level = os.environ.get("LOG_LEVEL", "DEBUG").upper()
    logging.basicConfig(level=getattr(logging, log_level))

    logger = logging.getLogger(__name__)

    version = get_app_version()
    logger.info(f"Starting up the '{service_name}' FastAPI app! Version: '{version}'")

    port = int(os.environ.get("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)  # tell uvicorn to use our logging config
