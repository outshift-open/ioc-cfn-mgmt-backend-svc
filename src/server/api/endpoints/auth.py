"""Authentication endpoints"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_

from server.auth.jwt import create_access_token, decode_token, verify_token_type
from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.user import User as UserModel
from server.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenRefreshResponse,
    TokenResponse,
)
from server.services.auth import auth_service

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(signup_data: SignupRequest):
    """
    Register a new user account.

    - **username**: Desired username (3-100 characters, alphanumeric with hyphens and underscores)
    - **email**: Email address
    - **password**: Password (minimum 8 characters)
    - **domain**: User domain (optional, default: ioc.local)
    - **role**: User role (optional, default: user)

    Returns JWT access token, refresh token, and user information
    """
    return auth_service.signup(
        username=signup_data.username,
        email=signup_data.email,
        password=signup_data.password,
        domain=signup_data.domain,
        role=signup_data.role,
    )


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(login_data: LoginRequest):
    """
    Authenticate user with username and password, return JWT tokens.

    - **username**: User's username
    - **password**: User's password

    Returns JWT access token (1 hour) and refresh token (7 days)
    """
    return auth_service.login(login_data.username, login_data.password)


@router.post("/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
def refresh_token(refresh_data: RefreshTokenRequest):
    """
    Refresh an access token using a valid refresh token.

    - **refresh_token**: Valid JWT refresh token

    Returns a new JWT access token
    """
    try:
        # Decode and validate refresh token
        payload = decode_token(refresh_data.refresh_token)
        verify_token_type(payload, "refresh")

        # Extract user info
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
            )

        # Get user info from database to ensure user still exists
        db = RelationalDB()
        session = db.get_session()

        try:
            user = (
                session.query(UserModel)
                .filter(
                    and_(
                        UserModel.id == user_id,
                        UserModel.deleted_at.is_(None),
                    )
                )
                .first()
            )

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or has been deleted",
                )

            # Create new access token
            access_token = create_access_token(
                data={
                    "sub": user.id,
                    "username": user.username,
                    "role": user.role,
                }
            )

            return TokenRefreshResponse(access_token=access_token, token_type="bearer")

        finally:
            session.close()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
        )
