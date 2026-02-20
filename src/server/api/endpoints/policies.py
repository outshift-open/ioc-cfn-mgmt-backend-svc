"""Policy API endpoints"""

from typing import Dict

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.policies import (
    PolicyCreate,
    PolicyDetail,
    PolicyList,
    PolicyUpdate,
)
from server.services.policies import policy_service

router = APIRouter()


@router.post(
    "/{workspace_id}/policies",
    response_model=PolicyDetail,
    summary="Create Policy",
    description="Create a new policy in workspace",
    status_code=201,
)
def create_policy(
    workspace_id: str,
    policy_data: PolicyCreate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new policy

    Args:
        workspace_id: Workspace identifier
        policy_data: Policy creation data
        auth_user: Authenticated user

    Returns:
        PolicyDetail with the created policy
    """
    authz_service.require_permission(auth_user, "create", "policy")
    user_id = auth_user.get("id", "unknown")
    return policy_service.create(workspace_id, policy_data, user_id)


@router.get(
    "/{workspace_id}/policies",
    response_model=PolicyList,
    summary="List Policies",
    description="Get list of all policies in workspace",
)
def list_policies(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all policies

    Args:
        workspace_id: Workspace identifier
        auth_user: Authenticated user

    Returns:
        PolicyList with all policies
    """
    authz_service.require_permission(auth_user, "list", "policy")
    return policy_service.list(workspace_id)


@router.get(
    "/{workspace_id}/policies/{policy_id}",
    response_model=PolicyDetail,
    summary="Get Policy",
    description="Get details of a specific policy",
)
def get_policy(
    workspace_id: str,
    policy_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific policy by ID

    Args:
        workspace_id: Workspace identifier
        policy_id: ID of the policy
        auth_user: Authenticated user

    Returns:
        PolicyDetail with the policy details
    """
    authz_service.require_permission(auth_user, "get", "policy")
    return policy_service.get(workspace_id, policy_id)


@router.patch(
    "/{workspace_id}/policies/{policy_id}",
    response_model=PolicyDetail,
    summary="Update Policy",
    description="Update an existing policy",
)
def update_policy(
    workspace_id: str,
    policy_id: str,
    update_data: PolicyUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a policy

    Args:
        workspace_id: Workspace identifier
        policy_id: ID of the policy to update
        update_data: Policy update data
        auth_user: Authenticated user

    Returns:
        PolicyDetail with the updated policy
    """
    authz_service.require_permission(auth_user, "update", "policy")
    user_id = auth_user.get("id", "unknown")
    return policy_service.update(workspace_id, policy_id, update_data, user_id)


@router.delete(
    "/{workspace_id}/policies/{policy_id}",
    response_model=Dict[str, str],
    summary="Delete Policy",
    description="Delete a policy (soft delete)",
)
def delete_policy(
    workspace_id: str,
    policy_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a policy (soft delete)

    Args:
        workspace_id: Workspace identifier
        policy_id: ID of the policy to delete
        auth_user: Authenticated user

    Returns:
        Dict with success message
    """
    authz_service.require_permission(auth_user, "delete", "policy")
    user_id = auth_user.get("id", "unknown")
    return policy_service.delete(workspace_id, policy_id, user_id)
