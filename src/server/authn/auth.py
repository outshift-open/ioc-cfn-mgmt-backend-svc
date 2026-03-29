# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Common API dependencies for authentication and authorization."""

from typing import Optional

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

# HTTP Bearer scheme for JWT tokens
bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_user(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    # x_api_key: Optional[str] = Header(None, alias="X-API-Key"),  # Uncomment if API key support is needed
) -> dict:
    """
    FastAPI dependency supporting dual authentication:
    1. JWT Bearer tokens (for UI users): Authorization: Bearer <token>
    2. API Keys (for programmatic access): X-API-Key: <key>

    Args:
        authorization: Optional Bearer token from Authorization header
        x_api_key: Optional API key from X-API-Key header

    Returns:
        dict: User information including id, username, role, and email

    Raises:
        HTTPException: 401 if no valid authentication provided
    """
    # Authentication disabled - return admin user
    # Use the same ID as ADMIN_USER_ID_DEFAULT in server.services.user
    return {
        "id": "00000000-0000-0000-0000-000000000000",
        "username": "admin",
        "role": "admin",
        "email": "admin@mock.local",
    }

    # # Try JWT token first (for UI users)
    # if authorization and authorization.credentials:
    #     try:
    #         payload = decode_token(authorization.credentials)
    #         verify_token_type(payload, "access")
    #
    #         user_id = payload.get("sub")
    #         username = payload.get("username")
    #         role = payload.get("role")
    #
    #         if not user_id or not username or not role:
    #             raise HTTPException(
    #                 status_code=status.HTTP_401_UNAUTHORIZED,
    #                 detail="Invalid token: missing user information",
    #                 headers={"WWW-Authenticate": "Bearer"},
    #             )
    #
    #         # Return user info from JWT token
    #         return {
    #             "id": user_id,
    #             "username": username,
    #             "role": role,
    #             "email": f"{username}@unknown",  # JWT doesn't have domain
    #         }
    #     except HTTPException:
    #         # If JWT validation fails, try API key as fallback
    #         pass
    #
    # # Try API key (for programmatic access)
    # if x_api_key:
    #     user_info = api_key_service.validate_api_key(x_api_key)
    #     if user_info:
    #         return user_info
    #
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid API key",
    #         headers={"WWW-Authenticate": "ApiKey"},
    #     )
    #
    # # No valid authentication provided
    # raise HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Authentication required. Provide either Authorization: Bearer <token> or X-API-Key: <key>",
    #     headers={"WWW-Authenticate": "Bearer"},
    # )
