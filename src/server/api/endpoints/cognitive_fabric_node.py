"""Cognitive Fabric Node API endpoints"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognitive_fabric_node import (
    CognitiveFabricNodeDetail,
    CognitiveFabricNodeHeartbeatResponse,
    CognitiveFabricNodeList,
    CognitiveFabricNodeRegisterRequest,
    CognitiveFabricNodeRegisterResponse,
    CognitiveFabricNodeUpdateRequest,
)
from server.services import cognitive_fabric_node_service

router = APIRouter()


def check_workspace_exists(workspace_id: str) -> None:
    """Check if workspace exists, raise 404 if not"""
    from server.services.workspace import workspace_service

    if not workspace_service.exists(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )


@router.post(
    "/{workspace_id}/create",
    response_model=CognitiveFabricNodeRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/{workspace_id}/register",
    response_model=CognitiveFabricNodeRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cfn_node(
    workspace_id: str,
    cfn_data: CognitiveFabricNodeRegisterRequest,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Create a new CFN node or refresh an active one

    - **cfn_id**: Persistent CFN identifier (provided by CFN, immutable)
    - **cfn_name**: Human-readable CFN name (can be updated later)
    - **cfn_config**: Optional current CFN configuration

    **Behavior by CFN State:**

    1. **New CFN or Deleted CFN (ID reuse)**: Creates new entry
       - Status: 201 Created
       - Returns: offline status with cloud_config

    2. **Active CFN (reboot/reconnection)**: Refreshes config
       - Status: 201 Created
       - Returns: offline status with cloud_config
       - Allows CFN to reconnect after reboot

    3. **Disabled CFN (ID locked)**: Rejects creation
       - Status: 403 Forbidden
       - CFN ID is locked and cannot be reused
       - Admin must manually enable it first via PATCH /enable

    **Response includes:**
    - **cfn_id**: The CFN identifier
    - **cfn_name**: The CFN name
    - **status**: Current status (offline)
    - **cloud_config**: Cloud configuration for the CFN to apply locally
      - workspace_id: Associated workspace
      - log_level: Logging level (e.g., INFO)
      - features: Enabled features list
      - updated_at: Configuration timestamp

    CFN must send heartbeat to change status from offline to online.
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "create", "cognitive_fabric_node")
    return cognitive_fabric_node_service.create(workspace_id, cfn_data, auth_user["id"])


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

    **Response includes:**
    - Full CFN details (cfn_id, workspace_id, cfn_name, cfn_config, status, last_seen, enabled, timestamps)
    - **cloud_config**: Regenerated cloud configuration for the CFN to apply
      - workspace_id: Associated workspace
      - log_level: Logging level
      - features: Enabled features list
      - updated_at: Configuration timestamp

    The cloud_config is automatically regenerated with each update to ensure CFN has the latest configuration.
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "update", "cognitive_fabric_node")
    return cognitive_fabric_node_service.update(workspace_id, cfn_id, cfn_data, auth_user["id"])


@router.patch(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}/enable",
    response_model=CognitiveFabricNodeDetail,
)
def enable_cfn_node(
    workspace_id: str,
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Enable a disabled CFN node

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier

    This is an admin operation to re-enable a disabled CFN.
    After enabling, the CFN can call /register to reconnect and resume operations.

    **Response includes:**
    - Full CFN details with enabled=True and status=offline (until heartbeat is sent)
    - **cloud_config**: Cloud configuration for the CFN to apply when it reconnects
      - workspace_id: Associated workspace
      - log_level: Logging level
      - features: Enabled features list
      - updated_at: Configuration timestamp
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "enable", "cognitive_fabric_node")
    return cognitive_fabric_node_service.enable(workspace_id, cfn_id, auth_user["id"])


@router.patch(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable",
    response_model=CognitiveFabricNodeDetail,
)
def disable_cfn_node(
    workspace_id: str,
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Disable CFN node (soft disable, prepares for deletion)

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier

    Disabling a CFN stops heartbeats and prepares it for deletion.
    The CFN will no longer appear in listings and cannot send heartbeats.
    The CFN ID is LOCKED and cannot be reused while in disabled state.

    After disabling, the "Delete" button will appear in the UI.
    The CFN can be re-enabled using the /enable endpoint, or permanently
    deleted using the DELETE endpoint.

    **Response includes:**
    - Full CFN details with enabled=False
    - **cloud_config**: Cloud configuration (preserved from last state)
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "disable", "cognitive_fabric_node")
    return cognitive_fabric_node_service.disable(workspace_id, cfn_id, auth_user["id"])


@router.delete(
    "/{workspace_id}/cognitive-fabric-node/{cfn_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_cfn_node(
    workspace_id: str,
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete CFN node (hard delete)

    - **workspace_id**: UUID of the workspace
    - **cfn_id**: CFN identifier

    **IMPORTANT:** A CFN must be disabled first before it can be deleted.

    Deleting a CFN marks it as deleted in the database.
    After deletion, the CFN ID can be reused to create a new CFN node.

    **Flow:**
    1. User clicks "Disable" in UI → CFN is disabled (PATCH /disable)
    2. "Delete" button appears in UI
    3. User clicks "Delete" → CFN is deleted (DELETE)
    4. CFN ID is now available for reuse

    No response body (204 No Content).
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "delete", "cognitive_fabric_node")
    cognitive_fabric_node_service.delete(workspace_id, cfn_id, auth_user["id"])
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
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "heartbeat", "cognitive_fabric_node")
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

    Returns a list of all CFN nodes (enabled and disabled) with summary information and total count.

    Deleted CFNs are never included.
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "list", "cognitive_fabric_node")
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

    Returns full CFN details including:
    - cfn_id, cfn_name
    - cfn_config (node-reported configuration)
    - cloud_config (cloud-side configuration to be applied)
    - status (online, offline, blocked)
    - enabled flag (true if CFN can operate, false if disabled)
    - created_at, updated_at, last_seen timestamps

    This endpoint retrieves information for both enabled and disabled CFNs.
    Deleted CFNs will return 404 Not Found.
    """
    check_workspace_exists(workspace_id)
    authz_service.require_permission(auth_user, "get", "cognitive_fabric_node")
    return cognitive_fabric_node_service.get(workspace_id, cfn_id)
