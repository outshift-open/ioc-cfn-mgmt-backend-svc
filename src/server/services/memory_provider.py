"""Memory Provider service - Business logic for Memory Provider operations

Memory Providers are shared across workspaces (cross-workspace resource).
They are associated with workspaces via the workspace_memory_provider join table.
"""

import logging
from datetime import datetime, timezone
from typing import List

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
from server.utils.encryption import process_config_for_display, process_config_for_storage


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

                # Convert Pydantic model to dict and encrypt credentials
                config_dict = provider_data.config.model_dump()
                config_dict = process_config_for_storage(config_dict)

                # Create new provider
                new_provider = MemoryProviderModel(
                    memory_provider_id=memory_provider_id,
                    memory_provider_name=provider_data.memory_provider_name,
                    description=provider_data.description,
                    config=config_dict,
                    enabled=True,
                    created_by=user_id,
                )

                session.add(new_provider)
                session.commit()
                session.refresh(new_provider)

                # Update all CFN configs since memory providers are global
                from server.services.cognition_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_all_cfns()

                return MemoryProviderDetail(
                    memory_provider_id=new_provider.memory_provider_id,
                    memory_provider_name=new_provider.memory_provider_name,
                    description=new_provider.description,
                    config=process_config_for_display(new_provider.config),
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
                    description=provider.description,
                    config=process_config_for_display(provider.config),
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
                        description=provider.description,
                        config=process_config_for_display(provider.config),
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
                if update_data.description is not None:
                    provider.description = update_data.description
                if update_data.config is not None:
                    # Convert Pydantic model to dict and encrypt credentials
                    updated_config = update_data.config.model_dump()
                    updated_config = process_config_for_storage(updated_config)
                    provider.config = updated_config
                if update_data.enabled is not None:
                    provider.enabled = update_data.enabled

                provider.updated_by = user_id
                provider.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(provider)

                # Update all CFN configs since memory providers are global
                from server.services.cognition_fabric_node import cognitive_fabric_node_service

                cognitive_fabric_node_service.update_config_for_all_cfns()

                return MemoryProviderDetail(
                    memory_provider_id=provider.memory_provider_id,
                    memory_provider_name=provider.memory_provider_name,
                    description=provider.description,
                    config=process_config_for_display(provider.config),
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
                from server.services.cognition_fabric_node import cognitive_fabric_node_service

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

    def list_for_cfn(self) -> List[dict]:
        """
        List Memory Providers with raw configs for CFN consumption

        This method bypasses the display masking and returns raw configs from the database
        so that process_config_for_cfn() can properly decrypt credentials for CFN nodes.

        Returns:
            List of dicts with raw provider data including encrypted credentials
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

                # Return raw provider data without masking
                return [
                    {
                        "memory_provider_id": provider.memory_provider_id,
                        "memory_provider_name": provider.memory_provider_name,
                        "description": provider.description,
                        "config": provider.config,  # Raw config with credentials_encrypted
                        "enabled": provider.enabled,
                    }
                    for provider in providers
                ]

            finally:
                session.close()

        except Exception as e:
            # Don't fail CFN config generation if memory providers can't be fetched
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to list memory providers for CFN: {str(e)}")
            return []


# Singleton instance
memory_provider_service = MemoryProviderService()
