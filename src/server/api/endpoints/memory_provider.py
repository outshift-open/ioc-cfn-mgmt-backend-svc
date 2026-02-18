"""Memory Provider API endpoints — Memory Providers are a cross-workspace resource"""

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.memory_provider import MemoryProviderList
from server.services.memory_provider import memory_provider_service

router = APIRouter()


@router.get(
    "/memory-providers",
    response_model=MemoryProviderList,
    summary="List Memory Providers",
    description="Get list of all memory providers (shared across workspaces)",
)
def list_memory_providers(
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all memory providers (global, not workspace-scoped)

    Args:
        auth_user: Authenticated user

    Returns:
        MemoryProviderList with all providers
    """
    authz_service.require_permission(auth_user, "list", "memory_provider")
    return memory_provider_service.list()
