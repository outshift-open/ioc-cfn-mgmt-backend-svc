"""Authentication service - Business logic for user authentication"""

import logging
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import and_

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.user import User as UserModel
from server.common import get_global_encryption_key, decrypt_data
from server.auth.jwt import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)


class AuthService:
    """Service layer for authentication business logic"""

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with username and password.

        Args:
            username: User's username
            password: User's plain text password

        Returns:
            User information dict if authentication succeeds, None otherwise
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Find user by username
                user = (
                    session.query(UserModel)
                    .filter(
                        and_(
                            UserModel.username == username,
                            UserModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if not user:
                    logger.warning(f"Authentication failed: User '{username}' not found")
                    return None

                # Decrypt stored password and compare
                key = get_global_encryption_key()
                stored_password = decrypt_data(user.password, key)  # type: ignore[arg-type]

                if stored_password != password:
                    logger.warning(f"Authentication failed: Invalid password for user '{username}'")
                    return None

                # Authentication successful
                logger.info(f"User '{username}' authenticated successfully")

                return {
                    "id": user.id,
                    "username": user.username,
                    "domain": user.domain,
                    "role": user.role,
                    "email": f"{user.username}@{user.domain}",
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error during authentication: {str(e)}")
            return None

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user and generate JWT tokens.

        Args:
            username: User's username
            password: User's plain text password

        Returns:
            Dictionary containing access_token, refresh_token, and token_type

        Raises:
            HTTPException: If authentication fails
        """
        user = self.authenticate_user(username, password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create JWT tokens
        access_token = create_access_token(data={"sub": user["id"], "username": user["username"], "role": user["role"]})
        refresh_token = create_refresh_token(data={"sub": user["id"]})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
        }


# Create singleton instance
auth_service = AuthService()
