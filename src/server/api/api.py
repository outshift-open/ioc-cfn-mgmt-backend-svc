from fastapi import APIRouter

from server.api.endpoints.workspaces import router as workspaces_router, internal_router as internal_workspaces_router
from server.api.endpoints.softwares import router as softwares_router
from server.api.endpoints.tkf import router as tkf_router
from server.api.endpoints.mas import router as mas_router
from server.api.endpoints.reasoners import router as reasoners_router
from server.api.endpoints.knowledge_adapters import router as kep_router
from server.api.endpoints.users import router as users_router
from server.api.endpoints.audit import router as audits_router
from server.api.endpoints.iam import router as iam_router


api_router = APIRouter()

api_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(internal_workspaces_router, prefix="/internal/workspaces", tags=["internal-workspaces"])
api_router.include_router(softwares_router, prefix="/softwares", tags=["softwares"])
api_router.include_router(mas_router, prefix="/workspaces", tags=["multi-agentic-systems"])
api_router.include_router(reasoners_router, prefix="/workspaces", tags=["reasoners"])
api_router.include_router(kep_router, prefix="/workspaces", tags=["knowledge-adapters"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(tkf_router, prefix="/tkf", tags=["tkf"])
api_router.include_router(audits_router, prefix="/audits", tags=["audits"])
api_router.include_router(iam_router, prefix="/iam", tags=["iam"])
