"""Memory Provider service - Business logic for Memory Provider operations

Memory Providers are shared across workspaces (cross-workspace resource).
They are associated with workspaces via the workspace_memory_provider join table.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.memory_provider import MemoryProvider as MemoryProviderModel
from server.schemas.memory_provider import (
    MemoryProviderCreate,
    MemoryProviderDetail,
    MemoryProviderList,
    MemoryProviderUpdate,
)
from server.utils import generate_uuid


class MemoryProviderService:
    """Service layer for Memory Provider business logic"""

    def create(self, provider_data: MemoryProviderCreate, user_id: str) -> MemoryProviderDetail:
        """
        Create a new Memory Provider

        Args:
            provider_data: Memory provider creation data
            user_id: ID of the user creating the provider

        Returns:
            MemoryProviderDetail with the created provider

        Raises:
            HTTPException: If provider with same name already exists or creation fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if provider with same name already exists (globally unique)
                existing_provider = (
                    session.query(MemoryProviderModel)
                    .filter(
                        MemoryProviderModel.memory_provider_name == provider_data.memory_provider_name,
                        MemoryProviderModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing_provider:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Memory provider with name '{provider_data.memory_provider_name}' already exists",
                    )

                # Generate unique ID for the provider
                memory_provider_id = generate_uuid()

                # Prepare config with default shared=False if not specified
                config = provider_data.config or {}
                if "shared" not in config:
                    config["shared"] = False

                # Create new provider
                new_provider = MemoryProviderModel(
                    memory_provider_id=memory_provider_id,
                    memory_provider_name=provider_data.memory_provider_name,
                    config=config,
                    enabled=True,
                    created_by=user_id,
                )

                session.add(new_provider)
                session.commit()
                session.refresh(new_provider)

                # Update all CFN configs since memory providers are global
                from server.services.cognitive_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_all_cfns()

                return MemoryProviderDetail(
                    memory_provider_id=new_provider.memory_provider_id,
                    memory_provider_name=new_provider.memory_provider_name,
                    config=new_provider.config,
                    enabled=new_provider.enabled,
                    created_at=new_provider.created_at,
                    updated_at=new_provider.updated_at,
                    created_by=new_provider.created_by,
                    updated_by=new_provider.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create memory provider: {str(e)}",
            )

    def get(self, memory_provider_id: str) -> MemoryProviderDetail:
        """
        Get a specific Memory Provider by ID

        Args:
            memory_provider_id: ID of the memory provider

        Returns:
            MemoryProviderDetail with the provider details

        Raises:
            HTTPException: If provider not found
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                provider = (
                    session.query(MemoryProviderModel)
                    .filter(
                        MemoryProviderModel.memory_provider_id == memory_provider_id,
                        MemoryProviderModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not provider:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Memory provider with ID '{memory_provider_id}' not found",
                    )

                return MemoryProviderDetail(
                    memory_provider_id=provider.memory_provider_id,
                    memory_provider_name=provider.memory_provider_name,
                    config=provider.config,
                    enabled=provider.enabled,
                    created_at=provider.created_at,
                    updated_at=provider.updated_at,
                    created_by=provider.created_by,
                    updated_by=provider.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get memory provider: {str(e)}",
            )

    def list(self) -> MemoryProviderList:
        """
        List all Memory Providers (global)

        Returns:
            MemoryProviderList with providers and total count
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                providers = (
                    session.query(MemoryProviderModel)
                    .filter(
                        MemoryProviderModel.deleted_at.is_(None),
                        MemoryProviderModel.enabled.is_(True),
                    )
                    .all()
                )

                provider_list = [
                    MemoryProviderDetail(
                        memory_provider_id=provider.memory_provider_id,
                        memory_provider_name=provider.memory_provider_name,
                        config=provider.config,
                        enabled=provider.enabled,
                        created_at=provider.created_at,
                        updated_at=provider.updated_at,
                        created_by=provider.created_by,
                        updated_by=provider.updated_by,
                    )
                    for provider in providers
                ]

                return MemoryProviderList(providers=provider_list, total=len(provider_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list memory providers: {str(e)}",
            )

    def update(self, memory_provider_id: str, update_data: MemoryProviderUpdate, user_id: str) -> MemoryProviderDetail:
        """
        Update a Memory Provider

        Args:
            memory_provider_id: ID of the memory provider to update
            update_data: Memory provider update data
            user_id: ID of the user updating the provider

        Returns:
            MemoryProviderDetail with the updated provider

        Raises:
            HTTPException: If provider not found or update fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                provider = (
                    session.query(MemoryProviderModel)
                    .filter(
                        MemoryProviderModel.memory_provider_id == memory_provider_id,
                        MemoryProviderModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not provider:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Memory provider with ID '{memory_provider_id}' not found",
                    )

                # Update fields if provided
                if update_data.memory_provider_name is not None:
                    provider.memory_provider_name = update_data.memory_provider_name
                if update_data.config is not None:
                    # Ensure shared field is present in config
                    updated_config = update_data.config.copy() if update_data.config else {}
                    if "shared" not in updated_config:
                        # Preserve existing shared value if present, otherwise default to False
                        existing_shared = (provider.config or {}).get("shared", False)
                        updated_config["shared"] = existing_shared
                    provider.config = updated_config
                if update_data.enabled is not None:
                    provider.enabled = update_data.enabled

                provider.updated_by = user_id
                provider.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(provider)

                # Update all CFN configs since memory providers are global
                from server.services.cognitive_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_all_cfns()

                return MemoryProviderDetail(
                    memory_provider_id=provider.memory_provider_id,
                    memory_provider_name=provider.memory_provider_name,
                    config=provider.config,
                    enabled=provider.enabled,
                    created_at=provider.created_at,
                    updated_at=provider.updated_at,
                    created_by=provider.created_by,
                    updated_by=provider.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update memory provider: {str(e)}",
            )

    def delete(self, memory_provider_id: str, user_id: str) -> dict:
        """
        Soft delete a Memory Provider

        Args:
            memory_provider_id: ID of the memory provider to delete
            user_id: ID of the user deleting the provider

        Returns:
            Dict with success message

        Raises:
            HTTPException: If provider not found or deletion fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                provider = (
                    session.query(MemoryProviderModel)
                    .filter(
                        MemoryProviderModel.memory_provider_id == memory_provider_id,
                        MemoryProviderModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not provider:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Memory provider with ID '{memory_provider_id}' not found",
                    )

                # Soft delete by setting deleted_at timestamp
                provider.deleted_at = datetime.now(timezone.utc)
                provider.updated_by = user_id
                provider.updated_at = datetime.now(timezone.utc)

                session.commit()

                # Update all CFN configs since memory providers are global
                from server.services.cognitive_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_all_cfns()

                return {
                    "message": f"Memory provider '{memory_provider_id}' deleted successfully",
                    "memory_provider_id": memory_provider_id,
                }

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete memory provider: {str(e)}",
            )


# Singleton instance
memory_provider_service = MemoryProviderService()
