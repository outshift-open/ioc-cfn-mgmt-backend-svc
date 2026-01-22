"""API Key service - Business logic for API key operations"""

import secrets
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_

from server.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyListItem,
    ApiKeyList,
)
from server.database.relational_db.models.api_key import ApiKey as ApiKeyModel
from server.database.relational_db.db import RelationalDB


class ApiKeyService:
    """Service layer for API key business logic"""

    KEY_PREFIX = "tkf_"
    KEY_LENGTH = 48  # Length of the random part (excluding prefix)
    PREVIEW_LENGTH = 15  # Number of characters to show in preview

    def _generate_api_key(self) -> str:
        """Generate a secure random API key with prefix"""
        random_part = secrets.token_urlsafe(self.KEY_LENGTH)
        # Remove any padding characters and limit length
        random_part = random_part.replace("-", "").replace("_", "")[:self.KEY_LENGTH]
        return f"{self.KEY_PREFIX}{random_part}"

    def _hash_api_key(self, api_key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _create_key_preview(self, api_key: str) -> str:
        """Create a preview of the API key (first N characters + ...)"""
        return f"{api_key[:self.PREVIEW_LENGTH]}..."

    def create_api_key(self, api_key_data: ApiKeyCreate) -> ApiKeyResponse:
        """Create a new API key"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Generate API key
                api_key = self._generate_api_key()
                key_hash = self._hash_api_key(api_key)
                key_preview = self._create_key_preview(api_key)

                # Create new API key record
                new_api_key = ApiKeyModel(
                    workspace_id=api_key_data.workspace_id,
                    key_hash=key_hash,
                    key_preview=key_preview,
                    name=api_key_data.name,
                    roles=api_key_data.roles,
                )

                session.add(new_api_key)
                session.commit()
                session.refresh(new_api_key)

                # Return response with the plain key (only time it's visible)
                return ApiKeyResponse(
                    id=new_api_key.id,  # type: ignore[arg-type]
                    key=api_key,
                    key_preview=key_preview,
                    name=new_api_key.name,  # type: ignore[arg-type]
                    roles=new_api_key.roles or [],  # type: ignore[arg-type]
                    workspace_id=new_api_key.workspace_id,  # type: ignore[arg-type]
                    created_at=new_api_key.created_at,  # type: ignore[arg-type]
                )

            finally:
                session.close()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create API key: {str(e)}",
            )

    def list_api_keys(self, workspace_id: Optional[str] = None) -> ApiKeyList:
        """List all active API keys, optionally filtered by workspace"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                query = session.query(ApiKeyModel).filter(ApiKeyModel.deleted_at.is_(None))

                # Filter by workspace if provided
                if workspace_id:
                    query = query.filter(ApiKeyModel.workspace_id == workspace_id)

                api_keys = query.all()

                api_key_items = [
                    ApiKeyListItem(
                        id=api_key.id,  # type: ignore[arg-type]
                        key_preview=api_key.key_preview,  # type: ignore[arg-type]
                        name=api_key.name,  # type: ignore[arg-type]
                        roles=api_key.roles or [],  # type: ignore[arg-type]
                        workspace_id=api_key.workspace_id,  # type: ignore[arg-type]
                        created_at=api_key.created_at,  # type: ignore[arg-type]
                    )
                    for api_key in api_keys
                ]

                return ApiKeyList(api_keys=api_key_items, total=len(api_key_items))

            finally:
                session.close()

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list API keys: {str(e)}",
            )

    def delete_api_key(self, key_id: str) -> dict:
        """Delete an API key (soft delete)"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                api_key = (
                    session.query(ApiKeyModel)
                    .filter(
                        and_(
                            ApiKeyModel.id == key_id,
                            ApiKeyModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not api_key:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="API key not found",
                    )

                # Soft delete
                api_key.deleted_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                session.commit()

                return {"message": "API key deleted successfully"}

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete API key: {str(e)}",
            )

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return associated user information.

        Args:
            api_key: The plain API key to validate

        Returns:
            dict with user information if valid, None otherwise
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Hash the provided key
                key_hash = self._hash_api_key(api_key)

                # Look up the key in the database
                api_key_record = (
                    session.query(ApiKeyModel)
                    .filter(
                        and_(
                            ApiKeyModel.key_hash == key_hash,
                            ApiKeyModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not api_key_record:
                    return None

                # Return user information based on the API key
                # The first role in the list is used as the primary role
                primary_role = api_key_record.roles[0] if api_key_record.roles else "viewer"  # type: ignore[index]

                return {
                    "id": api_key_record.id,
                    "username": api_key_record.name,
                    "role": primary_role,
                    "email": f"{api_key_record.name}@api.key",
                    "workspace_id": api_key_record.workspace_id,
                    "roles": api_key_record.roles,
                }

            finally:
                session.close()

        except Exception:
            return None


# Create singleton instance
api_key_service = ApiKeyService()
