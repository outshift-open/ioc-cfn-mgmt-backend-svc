# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter

from server.api.endpoints.audit_cfn_event import router as audit_cfn_events_router
from server.api.endpoints.knowledge_graph_cfn import router as knowledge_graph_cfn_router
from server.api.endpoints.auth import router as auth_router
from server.api.endpoints.cognition_engine import router as cognition_engine_router
from server.api.endpoints.cognition_fabric_node import router as cognition_fabric_node_router
from server.api.endpoints.iam import router as iam_router
from server.api.endpoints.memory_provider import router as memory_provider_router
from server.api.endpoints.multi_agentic_system import router as multi_agentic_system_router
from server.api.endpoints.policies import router as policy_router
from server.api.endpoints.workspace_invitations import (
    router as workspace_invitations_router,
)
from server.api.endpoints.workspace_members import router as workspace_members_router
from server.api.endpoints.workspaces import router as workspaces_router
from server.diagnostics import router as diagnostics_router

api_router = APIRouter()

api_router.include_router(cognition_fabric_node_router, prefix="", tags=["cognition-fabric-nodes"])
api_router.include_router(memory_provider_router, prefix="", tags=["memory-providers"])
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(multi_agentic_system_router, prefix="/workspaces", tags=["multi-agentic-systems"])
api_router.include_router(cognition_engine_router, prefix="/workspaces", tags=["cognition-engines"])
api_router.include_router(policy_router, prefix="/workspaces", tags=["policies"])
api_router.include_router(audit_cfn_events_router, prefix="/audit-events", tags=["audit-events"])
api_router.include_router(
    knowledge_graph_cfn_router,
    prefix="/workspaces/{workspaceId}/multi-agentic-systems/{masId}/knowledge-graph",
    tags=["knowledge-graph"],
)

api_router.include_router(
    diagnostics_router, prefix="/internal/diagnostics", tags=["diagnostics"], include_in_schema=False
)

# hidden endpoints
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"], include_in_schema=False)
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
