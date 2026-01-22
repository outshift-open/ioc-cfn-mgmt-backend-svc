from fastapi import APIRouter, Depends
from typing import Optional

from server.schemas.software import SoftwareList
from server.services import software_service
from server.api.dependencies import get_current_user
from server.authz.authz_service import authz_service

router = APIRouter()


@router.get("/", response_model=SoftwareList)
def list_softwares(
    type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    List all softwares, optionally filtered by type

    Args:
        type: Optional software type to filter by

    Returns:
        List of software items, filtered by type if specified
    """
    authz_service.require_permission(current_user, "get", "software")
    return software_service.list_softwares(type)
