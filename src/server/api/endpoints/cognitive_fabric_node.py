"""Cognitive Fabric Node API endpoints — CFNs are cross-workspace resources"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognitive_fabric_node import (
    CognitiveFabricNodeHeartbeatResponse,
    CognitiveFabricNodeList,
    CognitiveFabricNodeRegisterRequest,
    CognitiveFabricNodeResponse,
    CognitiveFabricNodeUpdateRequest,
)
from server.services import cognitive_fabric_node_service

router = APIRouter()


@router.post(
    "/cognitive-fabric-nodes",
    response_model=CognitiveFabricNodeResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/cognitive-fabric-nodes/register",
    response_model=CognitiveFabricNodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cfn_node(
    cfn_data: CognitiveFabricNodeRegisterRequest,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Register a new CFN node

    - **cfn_id**: Persistent CFN identifier (provided by CFN, immutable)
    - **cfn_name**: Human-readable CFN name (globally unique, can be updated later)
    - **cfn_config**: Optional current CFN configuration

    CFN is identifies to the management plane.
    Registration creates the CFN record without workspace association.
    Workspace association happens during workspace creation.

    **Response includes:**
    - **cfn_id**: The CFN identifier
    - **cfn_name**: The CFN name
    - **status**: Current status (offline)
    - **config**: Configuration for the CFN to apply locally
      - cognitive_fabric_node: CFN-specific operational settings (non-workspace scoped)
      - memory_providers: Global memory providers (non-workspace scoped)
      - workspaces: Associated workspaces with MAS, cognitive agents, engines

    CFN must send heartbeat to change status from offline to online.
    """
    authz_service.require_permission(auth_user, "create", "cognitive_fabric_node")
    return cognitive_fabric_node_service.create(cfn_data, auth_user["id"])


@router.put(
    "/cognitive-fabric-nodes/{cfn_id}",
    response_model=CognitiveFabricNodeResponse,
)
def update_cfn_node(
    cfn_id: str,
    cfn_data: CognitiveFabricNodeUpdateRequest,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Update CFN node information

    - **cfn_id**: CFN identifier (immutable)
    - **cfn_name**: Optional updated CFN name (globally unique)
    - **cfn_config**: Optional updated CFN configuration

    **Response includes:**
    - Full CFN details (cfn_id, workspace_ids, cfn_name, cfn_config, status, last_seen, enabled, timestamps)
    - **config**: Regenerated configuration for the CFN to apply
      - cognitive_fabric_node: CFN-specific operational settings
      - memory_providers: Global memory providers
      - workspaces: List of workspace details with MAS, cognitive agents, engines

    The config is automatically regenerated with each update to ensure CFN has the latest configuration.
    """
    authz_service.require_permission(auth_user, "update", "cognitive_fabric_node")
    return cognitive_fabric_node_service.update(cfn_id, cfn_data, auth_user["id"])


@router.patch(
    "/cognitive-fabric-nodes/{cfn_id}/enable",
    response_model=CognitiveFabricNodeResponse,
)
def enable_cfn_node(
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Enable a disabled CFN node

    - **cfn_id**: CFN identifier

    This is an admin operation to re-enable a disabled CFN.
    After enabling, the CFN can call /register to reconnect and resume operations.

    **Response includes:**
    - Full CFN details with enabled=True and status=offline (until heartbeat is sent)
    - **config**: Configuration for the CFN to apply when it reconnects
      - cognitive_fabric_node: CFN-specific operational settings
      - memory_providers: Global memory providers
      - workspaces: List of workspace details with MAS, cognitive agents, engines
    """
    authz_service.require_permission(auth_user, "enable", "cognitive_fabric_node")
    return cognitive_fabric_node_service.enable(cfn_id, auth_user["id"])


@router.patch(
    "/cognitive-fabric-nodes/{cfn_id}/disable",
    response_model=CognitiveFabricNodeResponse,
)
def disable_cfn_node(
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Disable CFN node (soft disable, prepares for deletion)

    - **cfn_id**: CFN identifier

    Disabling a CFN stops heartbeats and prepares it for deletion.
    The CFN will no longer be able to send heartbeats.
    The CFN ID is LOCKED and cannot be reused while in disabled state.

    After disabling, the "Delete" button will appear in the UI.
    The CFN can be re-enabled using the /enable endpoint, or permanently
    deleted using the DELETE endpoint.

    **Response includes:**
    - Full CFN details with enabled=False
    - **config**: Configuration (preserved from last state)
    """
    authz_service.require_permission(auth_user, "disable", "cognitive_fabric_node")
    return cognitive_fabric_node_service.disable(cfn_id, auth_user["id"])


@router.delete(
    "/cognitive-fabric-nodes/{cfn_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_cfn_node(
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Delete CFN node (hard delete)

    - **cfn_id**: CFN identifier

    **IMPORTANT:** A CFN must be disabled first before it can be deleted.

    Deleting a CFN marks it as deleted in the database and removes all
    workspace associations. After deletion, the CFN ID can be reused to
    create a new CFN node.

    **Flow:**
    1. User clicks "Disable" in UI → CFN is disabled (PATCH /disable)
    2. "Delete" button appears in UI
    3. User clicks "Delete" → CFN is deleted (DELETE)
    4. CFN ID is now available for reuse

    No response body (204 No Content).
    """
    authz_service.require_permission(auth_user, "delete", "cognitive_fabric_node")
    cognitive_fabric_node_service.delete(cfn_id, auth_user["id"])
    return None


@router.put(
    "/cognitive-fabric-nodes/{cfn_id}/heartbeat",
    response_model=CognitiveFabricNodeHeartbeatResponse,
)
def cfn_heartbeat(
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    CFN heartbeat endpoint - updates last_seen timestamp and returns config_timestamp

    - **cfn_id**: CFN identifier

    CFN nodes call this periodically (e.g., every 30 seconds) to indicate they are online.
    Returns the current status, last_seen timestamp, and config_timestamp.

    CFN compares the returned config_timestamp with its stored value.
    If timestamps differ, CFN should call GET /cognitive-fabric-nodes/{cfn_id} to fetch updated config.

    Note: This endpoint requires authentication but not write access.
    Disabled or deleted nodes will receive 403 Forbidden.
    """
    authz_service.require_permission(auth_user, "heartbeat", "cognitive_fabric_node")
    return cognitive_fabric_node_service.heartbeat(cfn_id)


@router.get(
    "/cognitive-fabric-nodes",
    response_model=CognitiveFabricNodeList,
)
def list_cfn_nodes(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace ID"),
    status: Optional[str] = Query(None, description="Filter by status (online, offline, blocked)"),
    auth_user: dict = Depends(get_auth_user),
):
    """
    List all CFN nodes, optionally filtered by workspace

    - **workspace_id**: Optional workspace filter
    - **status**: Optional status filter (online, offline, blocked)

    Returns all CFN nodes (enabled and disabled). Deleted CFNs are never included.
    """
    authz_service.require_permission(auth_user, "list", "cognitive_fabric_node")
    return cognitive_fabric_node_service.list(workspace_id, status)


@router.get(
    "/cognitive-fabric-nodes/{cfn_id}",
    response_model=CognitiveFabricNodeResponse,
)
def get_cfn_node(
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get detailed CFN node information

    - **cfn_id**: CFN identifier

    Returns full CFN details including:
    - cfn_id, cfn_name
    - workspace_ids (all associated workspaces)
    - cfn_config (node-reported configuration)
    - config (aggregated configuration to be applied)
    - status (online, offline)
    - enabled flag (true if CFN can operate, false if disabled)
    - created_at, updated_at, last_seen timestamps

    This endpoint retrieves information for both enabled and disabled CFNs.
    Deleted CFNs will return 404 Not Found.
    """
    authz_service.require_permission(auth_user, "get", "cognitive_fabric_node")
    return cognitive_fabric_node_service.get(cfn_id)


@router.get(
    "/cognitive-fabric-node/{cfn_id}/workspaces",
    response_model=dict,
)
def get_cfn_workspaces_config(
    cfn_id: str,
    auth_user: dict = Depends(get_auth_user),
):
    """
    Get aggregated workspace configuration for a CFN node

    This endpoint returns the consolidated configuration document that aggregates
    workspace-scoped and global resources for the CFN service to apply.

    - **cfn_id**: CFN identifier

    Returns configuration with:
    - **version**: Configuration schema version (0.1.0)
    - **cognitive_fabric_node**: List of CFN-specific operational settings (non-workspace scoped)
    - **memory_providers**: List of global memory providers (non-workspace scoped)
    - **workspaces**: List of workspaces with their resources:
      - workspace_id: Workspace identifier
      - workspace_name: Workspace name
      - multi_agent_systems: MAS available in this workspace
      - cognitive_agents: Cognitive agents in this workspace
      - cognitive_engines: Cognitive engines in this workspace (not included for March 2026)
      - policies: Policies in this workspace (not included for March 2026)
    """
    authz_service.require_permission(auth_user, "get", "cognitive_fabric_node")
    cfn = cognitive_fabric_node_service.get(cfn_id)
    if not cfn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CFN node not found",
        )
    return cfn.config
