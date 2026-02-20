"""Cognitive Agent API endpoints"""

from typing import Dict

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognitive_agent import (
    CognitiveAgentCreate,
    CognitiveAgentDetail,
    CognitiveAgentList,
    CognitiveAgentUpdate,
)
from server.services.cognitive_agent import cognitive_agent_service

router = APIRouter()


@router.post(
    "/{workspace_id}/cognitive-agents",
    response_model=CognitiveAgentDetail,
    summary="Create Cognitive Agent",
    description="Create a new cognitive agent in workspace",
    status_code=201,
)
def create_cognitive_agent(
    workspace_id: str,
    agent_data: CognitiveAgentCreate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new cognitive agent

    Args:
        workspace_id: Workspace identifier
        agent_data: Cognitive agent creation data
        auth_user: Authenticated user

    Returns:
        CognitiveAgentDetail with the created agent
    """
    authz_service.require_permission(auth_user, "create", "cognitive_agent")
    user_id = auth_user.get("id", "unknown")
    return cognitive_agent_service.create(workspace_id, agent_data, user_id)


@router.get(
    "/{workspace_id}/cognitive-agents",
    response_model=CognitiveAgentList,
    summary="List Cognitive Agents",
    description="Get list of all cognitive agents in workspace",
)
def list_cognitive_agents(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all cognitive agents

    Args:
        workspace_id: Workspace identifier
        auth_user: Authenticated user

    Returns:
        CognitiveAgentList with all agents
    """
    authz_service.require_permission(auth_user, "list", "cognitive_agent")
    return cognitive_agent_service.list(workspace_id)


@router.get(
    "/{workspace_id}/cognitive-agents/{cognitive_agent_id}",
    response_model=CognitiveAgentDetail,
    summary="Get Cognitive Agent",
    description="Get details of a specific cognitive agent",
)
def get_cognitive_agent(
    workspace_id: str,
    cognitive_agent_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get a specific cognitive agent by ID

    Args:
        workspace_id: Workspace identifier
        cognitive_agent_id: ID of the cognitive agent
        auth_user: Authenticated user

    Returns:
        CognitiveAgentDetail with the agent details
    """
    authz_service.require_permission(auth_user, "get", "cognitive_agent")
    return cognitive_agent_service.get(workspace_id, cognitive_agent_id)


@router.patch(
    "/{workspace_id}/cognitive-agents/{cognitive_agent_id}",
    response_model=CognitiveAgentDetail,
    summary="Update Cognitive Agent",
    description="Update an existing cognitive agent",
)
def update_cognitive_agent(
    workspace_id: str,
    cognitive_agent_id: str,
    update_data: CognitiveAgentUpdate,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update a cognitive agent

    Args:
        workspace_id: Workspace identifier
        cognitive_agent_id: ID of the cognitive agent to update
        update_data: Cognitive agent update data
        auth_user: Authenticated user

    Returns:
        CognitiveAgentDetail with the updated agent
    """
    authz_service.require_permission(auth_user, "update", "cognitive_agent")
    user_id = auth_user.get("id", "unknown")
    return cognitive_agent_service.update(workspace_id, cognitive_agent_id, update_data, user_id)


@router.delete(
    "/{workspace_id}/cognitive-agents/{cognitive_agent_id}",
    response_model=Dict[str, str],
    summary="Delete Cognitive Agent",
    description="Delete a cognitive agent (soft delete)",
)
def delete_cognitive_agent(
    workspace_id: str,
    cognitive_agent_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete a cognitive agent (soft delete)

    Args:
        workspace_id: Workspace identifier
        cognitive_agent_id: ID of the cognitive agent to delete
        auth_user: Authenticated user

    Returns:
        Dict with success message
    """
    authz_service.require_permission(auth_user, "delete", "cognitive_agent")
    user_id = auth_user.get("id", "unknown")
    return cognitive_agent_service.delete(workspace_id, cognitive_agent_id, user_id)
