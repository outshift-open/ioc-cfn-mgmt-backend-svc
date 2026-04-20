# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Knowledge Graph API endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.services.knowledge_graph_cfn import CfnUpstreamError, knowledge_graph_cfn_service

router = APIRouter()


@router.get(
    "",
    status_code=200,
    summary="Fetch Knowledge Graph",
    description="Retrieves the Knowledge Graph for a multi-agentic system.",
    responses={
        200: {"description": "Knowledge graph returned successfully"},
        400: {"description": "Invalid request"},
        404: {"description": "Knowledge graph not found"},
        500: {"description": "Internal server error"},
    },
)
def fetch_knowledge_graph(workspaceId: str, masId: str):
    """
    Fetch the knowledge graph for a MAS.

    - **workspaceId**: The Workspace ID (from path)
    - **masId**: The Multi-Agentic System ID (from path)
    """
    try:
        result = knowledge_graph_cfn_service.fetch_knowledge_graph(workspace_id=workspaceId, mas_id=masId)
        return JSONResponse(content=result)
    except CfnUpstreamError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"failed to fetch knowledge graph: {str(e)}"}
        )
