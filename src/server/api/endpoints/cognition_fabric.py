# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Fabric topology API endpoint"""

from collections import defaultdict

from fastapi import APIRouter, Depends

from server.authn.auth import get_auth_user
from server.authz.authz_service import authz_service
from server.schemas.cognition_fabric import (
    CognitionFabricNodeTopology,
    CognitionFabricTopologyResponse,
)
from server.schemas.memory_provider import MemoryProviderListItem
from server.services import cognition_fabric_node_service
from server.services.cognition_engine import cognition_engine_service
from server.services.memory_provider import memory_provider_service

router = APIRouter()


@router.get("", response_model=CognitionFabricTopologyResponse)
def get_cognition_fabric_topology(auth_user: dict = Depends(get_auth_user)):
    """Returns the full Cognition Fabric topology with nested CEs and memory providers per CFN."""
    authz_service.require_permission(auth_user, "list", "cognition_fabric_node")

    cfn_list = cognition_fabric_node_service.list()
    ce_list = cognition_engine_service.list()
    mp_list = memory_provider_service.list()

    # Group CEs by parent CFN
    ce_by_cfn = defaultdict(list)
    for ce in ce_list.cognition_engines:
        ce_by_cfn[ce.cfn_id].append(ce)

    # All enabled memory providers are global (broadcast to every CFN).
    # Project MemoryProviderDetail down to the slim list-item shape.
    enabled_providers = [
        MemoryProviderListItem(
            id=p.id,
            name=p.name,
            description=p.description,
            config=p.config,
            enabled=p.enabled,
            created_at=p.created_at,
        )
        for p in mp_list.providers
        if p.enabled
    ]

    cfn_nodes = [
        CognitionFabricNodeTopology(
            id=node.id,
            name=node.name,
            workspace_ids=node.workspace_ids,
            status=node.status,
            enabled=node.enabled,
            last_seen=str(node.last_seen),
            ip_address=getattr(node, "ip_address", None),
            port=getattr(node, "port", None),
            created_at=str(node.created_at),
            cognition_engines=ce_by_cfn.get(node.id, []),
            memory_providers=enabled_providers,
        )
        for node in cfn_list.nodes
    ]

    all_ces = ce_list.cognition_engines
    online_cfn = sum(1 for n in cfn_nodes if n.status == "online")
    online_ce = sum(1 for e in all_ces if e.status == "online")

    return CognitionFabricTopologyResponse(
        cognition_fabric_nodes=cfn_nodes,
        counts={
            "total_cfn_nodes": len(cfn_nodes),
            "online_cfn_nodes": online_cfn,
            "offline_cfn_nodes": len(cfn_nodes) - online_cfn,
            "total_cognition_engines": len(all_ces),
            "online_cognition_engines": online_ce,
            "offline_cognition_engines": len(all_ces) - online_ce,
            "total_memory_providers": len(enabled_providers),
        },
    )
