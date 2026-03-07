from fastapi import APIRouter

from server.api.endpoints.audit import router as audits_router
from server.api.endpoints.audit_cfn_event import router as audit_cfn_events_router
from server.api.endpoints.auth import router as auth_router
from server.api.endpoints.cognitive_agent import router as cognitive_agent_router
from server.api.endpoints.cognitive_engine import router as cognitive_engine_router
from server.api.endpoints.cognitive_fabric_node import router as cognitive_fabric_node_router
from server.api.endpoints.iam import router as iam_router
from server.api.endpoints.memory_provider import router as memory_provider_router
from server.api.endpoints.multi_agentic_system import router as multi_agentic_system_router
from server.api.endpoints.policies import router as policy_router
from server.api.endpoints.workspace_invitations import (
    router as workspace_invitations_router,
)
from server.api.endpoints.workspace_members import router as workspace_members_router
from server.api.endpoints.workspaces import router as workspaces_router

api_router = APIRouter()

api_router.include_router(cognitive_fabric_node_router, prefix="", tags=["cognitive-fabric-nodes"])
api_router.include_router(memory_provider_router, prefix="", tags=["memory-providers"])
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(multi_agentic_system_router, prefix="/workspaces", tags=["multi-agentic-systems"])
api_router.include_router(cognitive_agent_router, prefix="/workspaces", tags=["cognitive-agents"])
api_router.include_router(cognitive_engine_router, prefix="/workspaces", tags=["cognition-engines"])
api_router.include_router(policy_router, prefix="/workspaces", tags=["policies"])
api_router.include_router(audit_cfn_events_router, prefix="/audit-events", tags=["audit-events"])

# hidden endpoints
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"], include_in_schema=False)
api_router.include_router(audits_router, prefix="/audits", tags=["audits"], include_in_schema=False)
api_router.include_router(iam_router, prefix="/iam", tags=["iam"], include_in_schema=False)
api_router.include_router(
    workspace_invitations_router,
    prefix="",
    tags=["workspace-invitations"],
    include_in_schema=False,
)
api_router.include_router(
    workspace_members_router,
    prefix="",
    tags=["workspace-members"],
    include_in_schema=False,
)
