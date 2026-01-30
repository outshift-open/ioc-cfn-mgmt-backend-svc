"""Authentication schemas"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Schema for login request"""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class SignupRequest(BaseModel):
    """Schema for user sign-up request"""

    username: str = Field(..., min_length=3, max_length=100, description="Desired username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    domain: str = Field(default="ioc.local", description="User domain")
    role: str = Field(default="admin", description="User role")  # Every new user is an admin by default

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format"""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain alphanumeric characters, hyphens, and underscores")
        return v


class TokenResponse(BaseModel):
    """Schema for token response"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: dict = Field(..., description="User information")


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request"""

    refresh_token: str = Field(..., description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Schema for token refresh response"""

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
