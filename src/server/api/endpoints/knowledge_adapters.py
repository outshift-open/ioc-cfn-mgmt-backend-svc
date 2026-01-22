from fastapi import APIRouter, status, Depends

from server.schemas.knowledge_adapter import (
    KnowledgeAdapterRequest,
    KnowledgeAdapterResponse,
    KnowledgeAdapter,
    KnowledgeAdapters,
)
from server.services import knowledge_adapter_service
from server.api.dependencies import get_current_user
from server.authz.authz_service import authz_service

router = APIRouter()


@router.post(
    "/{workspace_id}/knowledge-adapters",
    response_model=KnowledgeAdapterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_adapter(
    workspace_id: str,
    kep_data: KnowledgeAdapterRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new Knowledge Adapter (KEP) within a workspace

    - **workspace_id**: UUID of the workspace
    - **name**: Friendly name for the KEP instance
    - **mas_ids**: List of MAS UUIDs this adapter serves
    - **type**: Data flow type (push, pull, or both)
    - **software_type**: Software type
    - **software_config**: Instance-specific configuration

    Returns the UUID and name of the created knowledge adapter
    """
    authz_service.require_permission(current_user, "create", "workspace")
    return knowledge_adapter_service.create_knowledge_adapter(workspace_id, kep_data)


@router.get(
    "/{workspace_id}/knowledge-adapters",
    response_model=KnowledgeAdapters,
)
def list_knowledge_adapters(
    workspace_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    List all Knowledge Adapters in a workspace

    - **workspace_id**: UUID of the workspace

    Returns list of knowledge adapters in the workspace
    """
    authz_service.require_permission(current_user, "get", "workspace")
    return knowledge_adapter_service.list_knowledge_adapters(workspace_id)


@router.get(
    "/{workspace_id}/knowledge-adapters/{kep_id}",
    response_model=KnowledgeAdapter,
)
def get_knowledge_adapter(
    workspace_id: str,
    kep_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific Knowledge Adapter by ID

    - **workspace_id**: UUID of the workspace
    - **kep_id**: UUID of the knowledge adapter

    Returns detailed knowledge adapter information
    """
    authz_service.require_permission(current_user, "get", "workspace")
    return knowledge_adapter_service.get_knowledge_adapter(workspace_id, kep_id)


@router.delete(
    "/{workspace_id}/knowledge-adapters/{kep_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_knowledge_adapter(
    workspace_id: str,
    kep_id: str,
    _purge: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a Knowledge Adapter

    - **workspace_id**: UUID of the workspace
    - **kep_id**: UUID of the knowledge adapter to delete
    - **_purge**: Optional query parameter. If false (default), performs soft delete. If true, performs hard delete.

    Returns success message
    """
    authz_service.require_permission(current_user, "delete", "workspace")
    knowledge_adapter_service.delete_knowledge_adapter(workspace_id, kep_id, _purge)
    return None
