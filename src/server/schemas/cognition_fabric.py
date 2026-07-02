# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Cognition Fabric topology aggregation schema"""

from typing import List

from pydantic import BaseModel, Field

from server.schemas.cognition_engine import CognitionEngineListItem
from server.schemas.memory_provider import MemoryProviderListItem


class CognitionFabricNodeTopology(BaseModel):
    """A CFN node with its nested cognition engines and memory providers"""

    id: str
    name: str
    workspace_ids: List[str] = Field(default_factory=list)
    status: str
    enabled: bool
    last_seen: str
    ip_address: str | None = None
    port: int | None = None
    created_at: str
    cognition_engines: List[CognitionEngineListItem] = Field(default_factory=list)
    memory_providers: List[MemoryProviderListItem] = Field(default_factory=list)


class CognitionFabricTopologyResponse(BaseModel):
    """Aggregated view of the entire Cognition Fabric topology"""

    cognition_fabric_nodes: List[CognitionFabricNodeTopology]
    counts: dict
