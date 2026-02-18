"""Authentication service - Business logic for user authentication"""

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_

from server.authn.jwt import create_access_token, create_refresh_token
from server.common import hash_password, verify_password
from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.user import User as UserModel

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

                # Verify password against stored hash
                if not verify_password(password, user.password):  # type: ignore[arg-type]
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

    def signup(
        self,
        username: str,
        email: str,
        password: str,
        domain: str = "ioc.local",
        role: str = "user",
    ) -> Dict[str, Any]:
        """
        Register a new user.

        Args:
            username: User's desired username
            email: User's email address
            password: User's password
            domain: User's domain (default: ioc.local)
            role: User's role (default: user)

        Returns:
            Dictionary containing user information and JWT tokens

        Raises:
            HTTPException: If username already exists or other validation errors occur
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if username already exists
                existing_user = (
                    session.query(UserModel)
                    .filter(
                        and_(
                            UserModel.username == username,
                            UserModel.deleted_at.is_(None),
                        )
                    )
                    .first()
                )

                if existing_user:
                    logger.warning(f"Sign-up failed: Username '{username}' already exists")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Username '{username}' is already taken",
                    )

                # Create new user
                user_id = str(uuid.uuid4())
                hashed_password = hash_password(password)

                new_user = UserModel(
                    id=user_id,
                    username=username,
                    password=hashed_password,
                    domain=domain,
                    role=role,
                )

                session.add(new_user)
                session.commit()

                logger.info(f"New user registered successfully - Username: {username}, Domain: {domain}, Role: {role}")

                # Note: Default workspace creation removed - workspaces require CFN assignment

                # Prepare user data
                user_data = {
                    "id": user_id,
                    "username": username,
                    "domain": domain,
                    "role": role,
                    "email": email,
                }

                # Create JWT tokens
                access_token = create_access_token(data={"sub": user_id, "username": username, "role": role})
                refresh_token = create_refresh_token(data={"sub": user_id})

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "user": user_data,
                }

            except HTTPException:
                raise
            except Exception as e:
                session.rollback()
                logger.error(f"Database error during sign-up: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error creating user: {str(e)}",
                )
            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during sign-up: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sign-up failed: {str(e)}",
            )


# Create singleton instance
auth_service = AuthService()
