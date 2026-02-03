"""Cognitive Fabric Node API endpoints"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from server.auth.auth import get_auth_user
from server.schemas.cognitive_fabric_node import (
    CognitiveFabricNodeDetail,
    CognitiveFabricNodeHeartbeatResponse,
    CognitiveFabricNodeList,
    CognitiveFabricNodeRegisterRequest,
    CognitiveFabricNodeRegisterResponse,
    CognitiveFabricNodeUpdateRequest,
)
from server.services import cognitive_fabric_node_service
from server.services.workspace_member import workspace_member_service

router = APIRouter()


def require_workspace_read_access(workspace_id: str, auth_user: dict) -> None:
    """Check if user has read access to workspace (admin or viewer)"""
    from server.services.workspace import workspace_service

    # Check if workspace exists first
    if not workspace_service.exists(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    user_role = auth_user.get("role")

    # Super admins have access to all workspaces
    if user_role == "super_admin":
        return

    # Check workspace membership - must be admin or viewer
    member_role = workspace_member_service.get_member_role(workspace_id, auth_user["id"])
    if member_role not in ["admin", "viewer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You must be a workspace admin or viewer",
        )


def require_workspace_write_access(workspace_id: str, auth_user: dict) -> None:
    """Check if user has write access to workspace (admin only)"""
    from server.services.workspace import workspace_service

    # Check if workspace exists first
    if not workspace_service.exists(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    user_role = auth_user.get("role")

    # Super admins have access to all workspaces
    if user_role == "super_admin":
        return

    # Check workspace membership - must be admin
    member_role = workspace_member_service.get_member_role(workspace_id, auth_user["id"])
    if member_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You must be a workspace admin",
        )


@router.post(
    "/{workspace_id}/cognitive-fabric-node/register",
    response_model=CognitiveFabricNodeRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_cfn_node(
    workspace_id: str,
    cfn_data: CognitiveFabricNodeRegisterRequest,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Register a new CFN node or re-enable a disabled one

    - **cfn_id**: Persistent CFN identifier (provided by CFN, immutable)
    - **cfn_name**: Human-readable CFN name (can be updated later)
    - **cfn_config**: Optional current CFN configuration

    Returns the cfn_id, cfn_name, status (offline), and cloud_config for the CFN to apply
    """
    require_workspace_write_access(workspace_id, auth_user)
    return cognitive_fabric_node_service.register(workspace_id, cfn_data, auth_user["id"])


@router.put(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}",
    response_model=CognitiveFabricNodeDetail,
)
def update_cfn_node(
    workspace_id: str,
    cfn_id: str,
    cfn_data: CognitiveFabricNodeUpdateRequest,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update CFN node information

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier (immutable)
    - **cfn_name**: Optional updated CFN name
    - **cfn_config**: Optional updated CFN configuration

    Returns full CFN details including updated cloud_config
    """
    require_workspace_write_access(workspace_id, auth_user)
    return cognitive_fabric_node_service.update(workspace_id, cfn_id, cfn_data, auth_user["id"])


@router.delete(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deregister_cfn_node(
    workspace_id: str,
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    De-register CFN node (soft delete/disable)

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier

    De-registering a CFN disables it by setting enabled=False and deleted_at timestamp.
    The CFN will no longer appear in listings and cannot send heartbeats.

    To re-enable, the CFN should call POST /register again (IoT-style registration).
    No response body (204 No Content).
    """
    require_workspace_write_access(workspace_id, auth_user)
    cognitive_fabric_node_service.deregister(workspace_id, cfn_id, auth_user["id"])
    return None


@router.put(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat",
    response_model=CognitiveFabricNodeHeartbeatResponse,
)
def cfn_heartbeat(
    workspace_id: str,
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    CFN heartbeat endpoint - updates last_seen timestamp

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier

    CFN nodes call this periodically (e.g., every 30 seconds) to indicate they are online.
    Returns the current status and last_seen timestamp.

    Note: This endpoint requires authentication but not write access.
    Disabled or de-registered nodes will receive 403 Forbidden.
    """
    require_workspace_read_access(workspace_id, auth_user)
    return cognitive_fabric_node_service.heartbeat(workspace_id, cfn_id)


@router.get(
    "/{workspace_id}/cognitive-fabric-node",
    response_model=CognitiveFabricNodeList,
)
def list_cfn_nodes(
    workspace_id: str,
    status: Optional[str] = Query(None, description="Filter by status (online, offline, blocked)"),
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all CFN nodes in workspace

    - **workspace_id**: UUID of the workspace
    - **status**: Optional status filter (online, offline, blocked)

    Returns a list of CFN nodes with summary information and total count.
    """
    require_workspace_read_access(workspace_id, auth_user)
    return cognitive_fabric_node_service.list(workspace_id, status)


@router.get(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}",
    response_model=CognitiveFabricNodeDetail,
)
def get_cfn_node(
    workspace_id: str,
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get detailed CFN node information

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier

    Returns full CFN details including configuration, status, and timestamps.
    """
    require_workspace_read_access(workspace_id, auth_user)
    return cognitive_fabric_node_service.get(workspace_id, cfn_id)
