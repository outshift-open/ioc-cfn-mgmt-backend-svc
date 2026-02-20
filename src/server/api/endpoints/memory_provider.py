"""Memory Provider API endpoints — Memory Providers are a cross-workspace resource"""

from typing import Dict

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.memory_provider import (
    MemoryProviderCreate,
    MemoryProviderDetail,
    MemoryProviderList,
    MemoryProviderUpdate,
)
from server.services.memory_provider import memory_provider_service

router = APIRouter()


@router.post(
    "/memory-providers",
    response_model=MemoryProviderDetail,
    summary="Create Memory Provider",
    description="Create a new memory provider (shared across workspaces)",
    status_code=201,
)
def create_memory_provider(
    provider_data: MemoryProviderCreate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new memory provider

    Args:
        provider_data: Memory provider creation data
        auth_user: Authenticated user

    Returns:
        MemoryProviderDetail with the created provider
    """
    authz_service.require_permission(auth_user, "create", "memory_provider")
    user_id = auth_user.get("sub", "unknown")
    return memory_provider_service.create(provider_data, user_id)


@router.get(
    "/memory-providers/{memory_provider_id}",
    response_model=MemoryProviderDetail,
    summary="Get Memory Provider",
    description="Get details of a specific memory provider",
)
def get_memory_provider(
    memory_provider_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific memory provider by ID

    Args:
        memory_provider_id: ID of the memory provider
        auth_user: Authenticated user

    Returns:
        MemoryProviderDetail with the provider details
    """
    authz_service.require_permission(auth_user, "read", "memory_provider")
    return memory_provider_service.get(memory_provider_id)


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


@router.patch(
    "/memory-providers/{memory_provider_id}",
    response_model=MemoryProviderDetail,
    summary="Update Memory Provider",
    description="Update an existing memory provider",
)
def update_memory_provider(
    memory_provider_id: str,
    update_data: MemoryProviderUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a memory provider

    Args:
        memory_provider_id: ID of the memory provider to update
        update_data: Memory provider update data
        auth_user: Authenticated user

    Returns:
        MemoryProviderDetail with the updated provider
    """
    authz_service.require_permission(auth_user, "update", "memory_provider")
    user_id = auth_user.get("sub", "unknown")
    return memory_provider_service.update(memory_provider_id, update_data, user_id)


@router.delete(
    "/memory-providers/{memory_provider_id}",
    response_model=Dict[str, str],
    summary="Delete Memory Provider",
    description="Delete a memory provider (soft delete)",
)
def delete_memory_provider(
    memory_provider_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a memory provider (soft delete)

    Args:
        memory_provider_id: ID of the memory provider to delete
        auth_user: Authenticated user

    Returns:
        Dict with success message
    """
    authz_service.require_permission(auth_user, "delete", "memory_provider")
    user_id = auth_user.get("sub", "unknown")
    return memory_provider_service.delete(memory_provider_id, user_id)
