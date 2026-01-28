"""UserTable service - Business logic for user operations"""

import logging
import uuid
import os
from datetime import datetime

from fastapi import HTTPException, status

from server.schemas.user import UserResponse, User, Users
from server.database.relational_db.models.user import User as UserModel
from server.database.relational_db.db import RelationalDB
from server.common import get_global_encryption_key, encrypt_data
from server.services.audit import AuditEventType, ResourceType, audit_service, AuditRequest

# Get logger instance (logging is setup in main.py)
logger = logging.getLogger(__name__)

# Admin user constants
ADMIN_USER_USERNAME_DEFAULT = "admin"
ADMIN_USER_PASSWORD_DEFAULT = "admin"
ADMIN_USER_DOMAIN_DEFAULT = "tkf.local"
ADMIN_USER_ROLE_DEFAULT = "admin"


class UserService:
    """Service layer for user business logic"""

    def create_admin_user(self) -> UserResponse:
        """
        Create a new admin user
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

                if existing_user:
                    logger.info(
                        f"Admin user '{ADMIN_USER_USERNAME_DEFAULT}' already exists with ID: {existing_user.id}"
                    )
                    # Return without API key since user already exists
                    return UserResponse(id=existing_user.id)

                # Create new admin user
                user_id = str(uuid.uuid4())
                password = os.getenv("ADMIN_USER_PASSWORD", ADMIN_USER_PASSWORD_DEFAULT)
                key = get_global_encryption_key()
                encrypted_password = encrypt_data(password, key)

                admin_user = UserModel(
                    id=user_id,
                    username=ADMIN_USER_USERNAME_DEFAULT,
                    password=encrypted_password,
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

                response = UserResponse(id=user_id)

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

    def list_users(self) -> Users:
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
                        id=user.id,
                        username=user.username,
                        domain=user.domain,
                        role=user.role,
                        created_at=user.created_at,
                        updated_at=user.updated_at,
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


# Global service instance
user_service = UserService()
