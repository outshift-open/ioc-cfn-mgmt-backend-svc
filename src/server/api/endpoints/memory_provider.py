"""Memory Provider API endpoints"""

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.memory_provider import MemoryProviderList
from server.services.memory_provider import memory_provider_service

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/memory-providers",
    response_model=MemoryProviderList,
    summary="List Memory Providers",
    description="Get list of all memory providers in workspace",
)
def list_memory_providers(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all memory providers

    Args:
        workspace_id: Workspace identifier
        auth_user: Authenticated user

    Returns:
        MemoryProviderList with all providers
    """
    # Check RBAC permissions
    authz_service.require_permission(auth_user, "list", "memory_provider")

    # Fetch providers from database
    return memory_provider_service.list(workspace_id)
