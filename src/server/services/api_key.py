"""API Key service - Business logic for API key operations"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.api_key import ApiKey as ApiKeyModel
from server.database.relational_db.models.user import User as UserModel
from server.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyList,
    ApiKeyListItem,
    ApiKeyResponse,
)


class ApiKeyService:
    """Service layer for API key business logic"""

    KEY_PREFIX = "ioc_"
    KEY_LENGTH = 48  # Length of the random part (excluding prefix)
    PREVIEW_LENGTH = 15  # Number of characters to show in preview

    def _generate_api_key(self) -> str:
        """Generate a secure random API key with prefix"""
        random_part = secrets.token_urlsafe(self.KEY_LENGTH)
        # Remove any padding characters and limit length
        random_part = random_part.replace("-", "").replace("_", "")[: self.KEY_LENGTH]
        return f"{self.KEY_PREFIX}{random_part}"

    def _hash_api_key(self, api_key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _create_key_preview(self, api_key: str) -> str:
        """Create a preview of the API key (first N characters + ...)"""
        return f"{api_key[:self.PREVIEW_LENGTH]}..."

    def create_api_key(self, api_key_data: ApiKeyCreate, user_id: str) -> ApiKeyResponse:
        """Create a new API key linked to a user"""
        db = RelationalDB()
        session = db.get_session()

        try:
            # Generate API key
            api_key = self._generate_api_key()
            key_hash = self._hash_api_key(api_key)
            key_preview = self._create_key_preview(api_key)

            # Create new API key record
            new_api_key = ApiKeyModel(
                user_id=user_id,
                key_hash=key_hash,
                key_preview=key_preview,
                name=api_key_data.name,
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
                user_id=new_api_key.user_id,  # type: ignore[arg-type]
                created_at=new_api_key.created_at,  # type: ignore[arg-type]
            )

        except IntegrityError as e:
            session.rollback()
            # Check if it's a unique constraint violation for the name
            if "idx_api_key_user_name_unique" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An API key with the name '{api_key_data.name}' already exists for this user",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create API key due to a database constraint",
            )
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create API key: {str(e)}",
            )
        finally:
            session.close()

    def list_api_keys(self, user_id: Optional[str] = None) -> ApiKeyList:
        """List all active API keys, optionally filtered by user"""
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                query = session.query(ApiKeyModel).filter(ApiKeyModel.deleted_at.is_(None))

                # Filter by user if provided
                if user_id:
                    query = query.filter(ApiKeyModel.user_id == user_id)

                api_keys = query.all()

                api_key_items = [
                    ApiKeyListItem(
                        id=api_key.id,  # type: ignore[arg-type]
                        key_preview=api_key.key_preview,  # type: ignore[arg-type]
                        name=api_key.name,  # type: ignore[arg-type]
                        user_id=api_key.user_id,  # type: ignore[arg-type]
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

    def delete_api_key(self, key_id: str, user_id: str, is_admin: bool = False) -> dict:
        """Delete an API key (soft delete)

        Args:
            key_id: ID of the API key to delete
            user_id: ID of the user requesting deletion
            is_admin: Whether the user is an admin
        """
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

                # Check ownership - users can only delete their own keys unless admin
                if not is_admin and api_key.user_id != user_id:  # type: ignore[attr-defined]
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only delete your own API keys",
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

                # Fetch the actual user from the User table (single source of truth)
                user = (
                    session.query(UserModel)
                    .filter(
                        and_(
                            UserModel.id == api_key_record.user_id,  # type: ignore[attr-defined]
                            UserModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not user:
                    return None

                # Return real user information (single source of truth for permissions)
                return {
                    "id": user.id,  # Real user ID
                    "username": user.username,  # Real username
                    "role": user.role,  # User's global role (single source of truth)
                    "email": f"{user.username}@{user.domain}",  # Real email
                    "api_key_id": api_key_record.id,  # For audit trails
                }

            finally:
                session.close()

        except Exception:
            return None


# Create singleton instance
api_key_service = ApiKeyService()
