"""Cognitive Engine API endpoints"""

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognitive_engine import CognitiveEngineList
from server.services.cognitive_engine import cognitive_engine_service

router = APIRouter()


@router.get(
    "/workspaces/{workspace_id}/cognitive-engines",
    response_model=CognitiveEngineList,
    summary="List Cognitive Engines",
    description="Get list of all cognitive engines in workspace",
)
def list_cognitive_engines(
    workspace_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all cognitive engines

    Args:
        workspace_id: Workspace identifier
        auth_user: Authenticated user

    Returns:
        CognitiveEngineList with all engines
    """
    # Check RBAC permissions
    authz_service.require_permission(auth_user, "list", "cognitive_engine")

    # Fetch engines from database
    return cognitive_engine_service.list(workspace_id)
