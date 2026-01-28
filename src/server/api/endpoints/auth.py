"""Authentication endpoints"""

from fastapi import APIRouter, status, HTTPException

from server.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, TokenRefreshResponse
from server.services.auth import auth_service
from server.auth.jwt import decode_token, verify_token_type, create_access_token

router = APIRouter()


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
        from server.database.relational_db.db import RelationalDB
        from server.database.relational_db.models.user import User as UserModel
        from sqlalchemy import and_

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
