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

    The API key is linked to the current authenticated user and inherits their role.
    Returns the created API key information including the full key (only shown once).
    """
    authz_service.require_permission(current_user, "create", "api_key")
    return api_key_service.create_api_key(api_key_data, user_id=current_user["id"])


@router.get(
    "/api-keys",
    response_model=ApiKeyList,
)
def list_api_keys(
    current_user: dict = Depends(get_current_user),
):
    """
    List API keys

    - Non-admin users see only their own API keys
    - Admin users see all API keys in the system

    Returns a list of API keys (without the full key value)
    """
    authz_service.require_permission(current_user, "get", "api_key")

    # Non-admins see only their own keys, admins see all
    user_id = None if current_user["role"] == "admin" else current_user["id"]

    return api_key_service.list_api_keys(user_id=user_id)


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

    Users can only delete their own API keys unless they are admins.
    Performs a soft delete of the API key.
    """
    authz_service.require_permission(current_user, "delete", "api_key")
    api_key_service.delete_api_key(key_id, user_id=current_user["id"], is_admin=current_user["role"] == "admin")
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
