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
from server.api.api import api_router
from server.common import service_name
from server.database.relational_db.db import RelationalDB
from server.services.cognitive_fabric_node_monitor import cognitive_fabric_node_monitor
from server.services.user import UserService
from server.services.workspace import WorkspaceService
from server.utils.version import get_app_version

# Load environment variables from .env file in current or parent directories
load_dotenv(override=True)

# Setup logging once for the entire application
setup_logging(service_name)

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

    logger.info("Database connections initialized")

    # Create admin user if not exists
    try:
        UserService().create_admin_user()
    except Exception as e:
        logger.error(f"Admin user creation failed: {str(e)}")
        raise

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

    logger.info("Closing database connection...")
    db.close()
    # await graph_db.close()
    logger.info("Database connection closed")


# Create FastAPI app
app = FastAPI(
    title=f"{service_name} API",
    version=get_app_version(),
    description="IOC CFN Management Backend Service API",
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
        "service": "ioc-cfn-mgmt-backend",
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

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
