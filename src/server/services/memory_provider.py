"""Memory Provider service - Business logic for Memory Provider operations"""

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.memory_provider import MemoryProvider as MemoryProviderModel
from server.schemas.memory_provider import MemoryProviderList, MemoryProviderListItem


class MemoryProviderService:
    """Service layer for Memory Provider business logic"""

    def list_dummy(self, workspace_id: str) -> MemoryProviderList:
        """Dummy implementation for listing memory providers"""
        dummy_provider = MemoryProviderListItem(
            memory_provider_id="dummy-id",
            workspace_id=workspace_id,
            memory_provider_name="Dummy Memory Provider",
            provider_type="dummy",
            provider="dummy",
            config={"type": "dummy", "version": "1.0"},
            enabled=True,
            created_at="2024-01-01T00:00:00Z",
        )
        return MemoryProviderList(providers=[dummy_provider], total=1)

    def list(self, workspace_id: str) -> MemoryProviderList:
        """
        List all Memory Providers in workspace

        Args:
            workspace_id: Workspace identifier

        Returns:
            MemoryProviderList with providers and total count
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Query all enabled providers in workspace
                providers = (
                    session.query(MemoryProviderModel)
                    .filter(
                        MemoryProviderModel.workspace_id == workspace_id,
                        MemoryProviderModel.deleted_at.is_(None),
                        MemoryProviderModel.enabled.is_(True),
                    )
                    .all()
                )

                provider_list = [
                    MemoryProviderListItem(
                        memory_provider_id=provider.memory_provider_id,
                        workspace_id=provider.workspace_id,
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
