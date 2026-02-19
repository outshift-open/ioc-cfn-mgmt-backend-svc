"""UserTable service - Business logic for user operations"""

import hashlib
import logging
import os
import uuid
from datetime import datetime

from fastapi import HTTPException, status

from server.common import hash_password
from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.api_key import ApiKey as ApiKeyModel
from server.database.relational_db.models.user import User as UserModel
from server.schemas.user import User, UserResponse, Users
from server.services.audit import (
    AuditEventType,
    AuditRequest,
    ResourceType,
    audit_service,
)

# Get logger instance (logging is setup in main.py)
logger = logging.getLogger(__name__)

# Admin user constants
ADMIN_USER_ID_DEFAULT = "00000000-0000-0000-0000-000000000000"  # Hardcoded for dev/testing
ADMIN_USER_USERNAME_DEFAULT = "admin"
ADMIN_USER_PASSWORD_DEFAULT = "admin"
ADMIN_USER_DOMAIN_DEFAULT = "ioc.local"
ADMIN_USER_ROLE_DEFAULT = "admin"
ADMIN_WORKSPACE_ID_DEFAULT = "00000000-0000-0000-0000-000000000001"  # Hardcoded for dev/testing
ADMIN_API_KEY_DEFAULT = "ioc_admin_default_key_for_testing_only_do_not_use_in_prod"  # Fixed API key for testing


class UserService:
    """Service layer for user business logic"""

    def create_admin_user(self) -> UserResponse:
        """
        Create a new admin user and their default workspace
        Kept as a separate function for future expansion to the admin user functionality
        Returns:
            UserResponse with the created user ID
        Raises:
            HTTPException: If error
        """
        logger.info("Starting admin user creation process")

        try:
            # Get database instance
            logger.debug("Initializing database connection")
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if admin user already exists
                existing_user = (
                    session.query(UserModel)
                    .filter(UserModel.username == ADMIN_USER_USERNAME_DEFAULT, UserModel.deleted_at.is_(None))
                    .first()
                )

                user_id = None

                if existing_user:
                    logger.info(
                        f"Admin user '{ADMIN_USER_USERNAME_DEFAULT}' already exists with ID: {existing_user.id}"
                    )
                    user_id = str(existing_user.id)
                else:
                    # Create new admin user with hardcoded ID for dev/testing
                    user_id = ADMIN_USER_ID_DEFAULT
                    password = os.getenv("ADMIN_USER_PASSWORD", ADMIN_USER_PASSWORD_DEFAULT)
                    hashed_password = hash_password(password)

                    admin_user = UserModel(
                        id=user_id,
                        username=ADMIN_USER_USERNAME_DEFAULT,
                        password=hashed_password,
                        domain=ADMIN_USER_DOMAIN_DEFAULT,
                        role=ADMIN_USER_ROLE_DEFAULT,
                    )

                    # Add to database
                    session.add(admin_user)
                    session.commit()

                    logger.info(
                        f"Successfully created admin user - "
                        f"Username: {ADMIN_USER_USERNAME_DEFAULT}, "
                        f"Domain: {ADMIN_USER_DOMAIN_DEFAULT}, "
                        f"Role: {ADMIN_USER_ROLE_DEFAULT} "
                        f"with ID: {user_id}"
                    )

                    # add to audits table
                    audit_service.create_audit(
                        AuditRequest(
                            resource_type=ResourceType.USER,
                            audit_type=AuditEventType.RESOURCE_CREATED,
                            audit_resource_id=user_id,
                            created_by="",  # TODO: get user from apikey
                            audit_information={
                                "username": ADMIN_USER_USERNAME_DEFAULT,
                                "domain": ADMIN_USER_DOMAIN_DEFAULT,
                                "role": ADMIN_USER_ROLE_DEFAULT,
                            },
                            audit_extra_information="success",
                            created_at=datetime.utcnow(),
                        )
                    )

                # Create or get default API key for admin user
                api_key_hash = hashlib.sha256(ADMIN_API_KEY_DEFAULT.encode()).hexdigest()
                api_key_preview = ADMIN_API_KEY_DEFAULT[:15] + "..."

                # Check if API key already exists
                existing_api_key = (
                    session.query(ApiKeyModel)
                    .filter(
                        ApiKeyModel.user_id == user_id,
                        ApiKeyModel.deleted_at.is_(None),
                        ApiKeyModel.name == "Admin Default API Key",
                    )
                    .first()
                )

                if not existing_api_key:
                    # Create the API key
                    admin_api_key = ApiKeyModel(
                        user_id=user_id,
                        key_hash=api_key_hash,
                        key_preview=api_key_preview,
                        name="Admin Default API Key",
                    )
                    session.add(admin_api_key)
                    session.commit()
                    logger.info(f"Created default API key for admin user: {api_key_preview}")
                else:
                    logger.info(f"Default API key for admin user already exists: {api_key_preview}")

                response = UserResponse(id=user_id, api_key=ADMIN_API_KEY_DEFAULT, api_key_preview=api_key_preview)
                return response

            except Exception as e:
                session.rollback()
                logger.error(f"Database error while creating admin user: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}"
                )
            finally:
                session.close()
                logger.debug("Database session closed")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating admin user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating admin user: {str(e)}"
            )

    def list(self) -> Users:
        """
        Get all users from the database

        Returns:
            Users: List of users with total count
        Raises:
            HTTPException: If database error occurs
        """
        logger.info("Retrieving all active users")

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                users = session.query(UserModel).filter(UserModel.deleted_at.is_(None)).all()

                user_details = [
                    User(
                        id=str(user.id),
                        username=str(user.username),
                        domain=str(user.domain),
                        role=str(user.role),
                        created_at=user.created_at,  # type: ignore[arg-type]
                        updated_at=user.updated_at,  # type: ignore[arg-type]
                    )
                    for user in users
                ]

                logger.info(f"Retrieved {len(user_details)} users")
                return Users(users=user_details, total=len(user_details))

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error retrieving users: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving users: {str(e)}"
            )

    def get(self, user_id: str) -> User:
        """
        Get a specific user by ID

        Args:
            user_id: The user ID to retrieve

        Returns:
            User: The requested user

        Raises:
            HTTPException: If user not found or database error occurs
        """
        logger.info(f"Retrieving user with ID: {user_id}")

        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                user = session.query(UserModel).filter(UserModel.id == user_id, UserModel.deleted_at.is_(None)).first()

                if not user:
                    logger.warning(f"User with ID '{user_id}' not found")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User with ID '{user_id}' not found",
                    )

                return User(
                    id=str(user.id),
                    username=str(user.username),
                    domain=str(user.domain),
                    role=str(user.role),
                    created_at=user.created_at,  # type: ignore[arg-type]
                    updated_at=user.updated_at,  # type: ignore[arg-type]
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving user: {str(e)}"
            )


# Global service instance
user_service = UserService()
