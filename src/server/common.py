import os
import logging
import bcrypt

# Get logger instance (logging is setup in main.py)
logger = logging.getLogger(__name__)

service_name = os.environ.get("SERVICE_NAME", "ioc-cfn-mgmt-backend")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Raises:
        Exception: If hashing fails

    Note:
        bcrypt has a maximum password length of 72 bytes. Passwords longer than
        72 bytes are automatically truncated.
    """
    try:
        # bcrypt has a 72-byte limit. Manually truncate to avoid errors with newer bcrypt versions
        # Encode to bytes first to count actual bytes, not characters
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            # Truncate to 72 bytes
            password_bytes = password_bytes[:72]

        # Generate salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise

    Raises:
        Exception: If verification fails
    """
    try:
        # Encode password to bytes
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > 72:
            # Truncate to 72 bytes (same as during hashing)
            password_bytes = password_bytes[:72]

        # Verify password
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        raise
