"""IAM (Identity and Access Management) endpoints"""

from fastapi import APIRouter, status, Depends
from typing import List

from server.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyList
from server.schemas.user import Users
from server.services.api_key import api_key_service
from server.services.user import user_service
from server.api.dependencies import get_current_user
from server.authz.authz_service import authz_service


router = APIRouter()


@router.post(
    "/api-keys",
    response_model=ApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    api_key_data: ApiKeyCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new API key

    - **name**: Human-readable name for the API key
    - **roles**: List of roles to assign to this key (e.g., ["admin", "viewer"])
    - **workspace_id**: Optional workspace ID to associate with the key

    Returns the created API key information including the full key (only shown once)
    """
    authz_service.require_permission(current_user, "create", "api_key")
    return api_key_service.create_api_key(api_key_data)


@router.get(
    "/api-keys",
    response_model=ApiKeyList,
)
def list_api_keys(
    workspace_id: str = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List all API keys

    - **workspace_id**: Optional query parameter to filter by workspace

    Returns a list of all API keys (without the full key value)
    """
    authz_service.require_permission(current_user, "get", "api_key")
    return api_key_service.list_api_keys(workspace_id=workspace_id)


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete an API key

    - **key_id**: UUID of the API key to delete

    Performs a soft delete of the API key
    """
    authz_service.require_permission(current_user, "delete", "api_key")
    api_key_service.delete_api_key(key_id)
    return None


@router.get(
    "/roles",
    response_model=List[str],
)
def list_roles(
    current_user: dict = Depends(get_current_user),
):
    """
    List all available IAM roles

    Returns a list of role names that can be assigned to API keys
    """
    authz_service.require_permission(current_user, "get_roles", "iam")
    return ["admin", "viewer", "guest"]


@router.get(
    "/users",
    response_model=Users,
)
def list_iam_users(
    current_user: dict = Depends(get_current_user),
):
    """
    List all users in the system

    Returns a list of all users with their basic information
    """
    # Note: Using 'user' as resource for consistency with authz policies
    authz_service.require_permission(current_user, "get", "user")
    return user_service.list_users()
