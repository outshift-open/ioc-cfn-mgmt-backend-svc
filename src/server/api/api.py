from fastapi import APIRouter

from server.api.endpoints.audit import router as audits_router
from server.api.endpoints.auth import router as auth_router
from server.api.endpoints.iam import router as iam_router
from server.api.endpoints.mas import router as mas_router
from server.api.endpoints.workspace_invitations import (
    router as workspace_invitations_router,
)
from server.api.endpoints.workspace_members import router as workspace_members_router
from server.api.endpoints.workspaces import (
    internal_router as internal_workspaces_router,
)
from server.api.endpoints.workspaces import router as workspaces_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(internal_workspaces_router, prefix="/internal/workspaces", tags=["internal-workspaces"])
api_router.include_router(mas_router, prefix="/workspaces", tags=["multi-agentic-systems"])
api_router.include_router(audits_router, prefix="/audits", tags=["audits"])
api_router.include_router(iam_router, prefix="/iam", tags=["iam"])
api_router.include_router(workspace_invitations_router, prefix="", tags=["workspace-invitations"])
api_router.include_router(workspace_members_router, prefix="", tags=["workspace-members"])
