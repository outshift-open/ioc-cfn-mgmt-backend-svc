"""Common API dependencies for authentication and authorization."""

from typing import Optional

from fastapi import Header, HTTPException, status

from server.services.api_key import api_key_service


async def get_current_user(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> dict:
    """
    FastAPI dependency to extract and validate API key from header.

    For development/testing, returns mock admin user if no key provided.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        dict: User information including id, role, and email
    """
    # For development/testing, allow requests without API key as admin
    if x_api_key is None:
        return {
            "id": "dev-user",
            "username": "dev-user",
            "role": "admin",
            "email": "dev@example.com",
        }

    # Validate API key using the database
    user_info = api_key_service.validate_api_key(x_api_key)

    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return user_info
