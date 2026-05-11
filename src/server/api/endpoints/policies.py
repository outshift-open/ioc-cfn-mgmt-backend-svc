# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

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
    authz_service.require_permission(auth_user, "list", "policy")
    return policy_service.list(workspace_id)


@router.get(
    "/{workspace_id}/policies/{id}",
    response_model=PolicyDetail,
    summary="Get Policy",
    description="Get details of a specific policy",
)
def get_policy(
    workspace_id: str,
    id: str,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "get", "policy")
    return policy_service.get(workspace_id, id)


@router.patch(
    "/{workspace_id}/policies/{id}",
    response_model=PolicyDetail,
    summary="Update Policy",
    description="Update an existing policy",
)
def update_policy(
    workspace_id: str,
    id: str,
    update_data: PolicyUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "update", "policy")
    user_id = auth_user.get("id", "unknown")
    return policy_service.update(workspace_id, id, update_data, user_id)


@router.delete(
    "/{workspace_id}/policies/{id}",
    response_model=Dict[str, str],
    summary="Delete Policy",
    description="Delete a policy (soft delete)",
)
def delete_policy(
    workspace_id: str,
    id: str,
    auth_user: dict = Depends(get_auth_user),
):
    authz_service.require_permission(auth_user, "delete", "policy")
    user_id = auth_user.get("id", "unknown")
    return policy_service.delete(workspace_id, id, user_id)
