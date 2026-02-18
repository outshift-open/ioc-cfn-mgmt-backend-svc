"""Memory Provider service - Business logic for Memory Provider operations

Memory Providers are shared across workspaces (cross-workspace resource).
They are associated with workspaces via the workspace_memory_provider join table.
"""

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.memory_provider import MemoryProvider as MemoryProviderModel
from server.schemas.memory_provider import MemoryProviderList, MemoryProviderListItem


class MemoryProviderService:
    """Service layer for Memory Provider business logic"""

    def list_dummy(self) -> MemoryProviderList:
        """Dummy implementation for listing memory providers"""
        dummy_provider = MemoryProviderListItem(
            memory_provider_id="dummy-id",
            memory_provider_name="Dummy Memory Provider",
            provider_type="dummy",
            provider="dummy",
            config={"version": "1.0"},
            enabled=True,
            created_at="2024-01-01T00:00:00Z",
        )
        return MemoryProviderList(providers=[dummy_provider], total=1)

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
                    MemoryProviderListItem(
                        memory_provider_id=provider.memory_provider_id,
                        memory_provider_name=provider.memory_provider_name,
                        provider_type=provider.provider_type,
                        provider=provider.provider,
                        config=provider.config,
                        enabled=provider.enabled,
                        created_at=provider.created_at.isoformat() if provider.created_at else None,
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


# Singleton instance
memory_provider_service = MemoryProviderService()
