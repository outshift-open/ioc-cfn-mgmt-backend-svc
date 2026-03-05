"""Encryption utilities for sensitive data"""

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


KEY_FILE = Path(__file__).parent.parent.parent.parent / ".secrets" / "encryption.key"


def get_or_create_encryption_key() -> str:
    """
    Get encryption key from environment variable or local file.
    Auto-generates and stores key if neither exists.

    Priority:
    1. MEMORY_PROVIDER_ENCRYPTION_KEY environment variable (for CI/production)
    2. .secrets/encryption.key file (for local development)
    3. Auto-generate new key and save to file

    Returns:
        Encryption key as string
    """
    if env_key := os.getenv("MEMORY_PROVIDER_ENCRYPTION_KEY"):
        logger.info("Using encryption key from environment variable")
        return env_key

    if KEY_FILE.exists():
        logger.info(f"Using encryption key from {KEY_FILE}")
        return KEY_FILE.read_text().strip()

    logger.warning("No encryption key found - generating new one")

    KEY_FILE.parent.mkdir(exist_ok=True)

    new_key = Fernet.generate_key().decode()

    KEY_FILE.write_text(new_key)
    try:
        KEY_FILE.chmod(0o600)
    except Exception:
        pass

    logger.warning(f"Generated new encryption key and saved to {KEY_FILE}")
    logger.warning(" Keep this file safe - deleting it will make existing encrypted data unreadable!")
    logger.warning(" This key is unique to your local environment")

    return new_key


ENCRYPTION_KEY = get_or_create_encryption_key()
cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_credentials(credentials: dict) -> str:
    """
    Encrypt credentials dictionary to encrypted string

    Args:
        credentials: Dict with sensitive fields like api_key, password, etc.

    Returns:
        Base64-encoded encrypted string

    Raises:
        ValueError: If credentials is empty or invalid format
        RuntimeError: If encryption operation fails
    """
    if not credentials:
        raise ValueError("Cannot encrypt empty credentials")

    try:
        # Serialize to JSON
        json_bytes = json.dumps(credentials).encode("utf-8")

        # Encrypt
        encrypted_bytes = cipher.encrypt(json_bytes)

        # Return as string for JSONB storage
        return encrypted_bytes.decode("utf-8")
    except (TypeError, ValueError) as e:
        logger.error("Failed to encrypt credentials: invalid format")
        raise ValueError("Invalid credentials format") from e
    except Exception as e:
        logger.error("Encryption operation failed")
        raise RuntimeError("Encryption failed") from e


def decrypt_credentials(encrypted: str) -> dict:
    """
    Decrypt encrypted credentials string to dictionary

    Args:
        encrypted: Base64-encoded encrypted string

    Returns:
        Decrypted credentials dictionary

    Raises:
        ValueError: If encrypted string is empty or invalid format
        RuntimeError: If decryption operation fails
    """
    if not encrypted:
        raise ValueError("Cannot decrypt empty string")

    try:
        # Decrypt
        encrypted_bytes = encrypted.encode("utf-8")
        decrypted_bytes = cipher.decrypt(encrypted_bytes)

        # Parse JSON
        credentials = json.loads(decrypted_bytes.decode("utf-8"))

        return credentials
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to decrypt credentials: invalid format or corrupted data")
        raise ValueError("Invalid encrypted credentials format") from e
    except Exception as e:
        logger.error("Decryption operation failed")
        raise RuntimeError("Decryption failed") from e


def process_config_for_storage(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process config before storing in database - encrypt credentials

    Args:
        config: Memory provider config dict

    Returns:
        Config with credentials encrypted
    """
    config_copy = copy.deepcopy(config)

    # Check if auth has credentials
    if config_copy.get("auth", {}).get("type") != "none":
        credentials = config_copy.get("auth", {}).get("credentials")

        if credentials:
            # Encrypt credentials (always, since cipher is required)
            encrypted = encrypt_credentials(credentials)
            config_copy["auth"]["credentials_encrypted"] = encrypted
            del config_copy["auth"]["credentials"]

    return config_copy


def process_config_for_cfn(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process config before sending to CFN - decrypt credentials

    Args:
        config: Memory provider config dict from database

    Returns:
        Config with credentials decrypted
    """
    config_copy = copy.deepcopy(config)

    # Check if auth has encrypted credentials
    if config_copy.get("auth", {}).get("credentials_encrypted"):
        encrypted = config_copy["auth"]["credentials_encrypted"]

        # Decrypt credentials
        decrypted = decrypt_credentials(encrypted)

        if decrypted:
            config_copy["auth"]["credentials"] = decrypted
            del config_copy["auth"]["credentials_encrypted"]

    return config_copy


def process_config_for_display(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Process config before returning in API response - mask sensitive credentials
    Only returns fields relevant to the specific auth type.

    Args:
        config: Memory provider config dict from database

    Returns:
        Config with sensitive credential fields masked as ***ENCRYPTED***
    """
    if not config:
        return config
    config_copy = copy.deepcopy(config)

    # Check if auth has encrypted credentials
    if config_copy.get("auth", {}).get("credentials_encrypted"):
        encrypted = config_copy["auth"]["credentials_encrypted"]
        del config_copy["auth"]["credentials_encrypted"]

        # Decrypt to get the structure of what was stored
        decrypted = decrypt_credentials(encrypted)

        # Get auth type to filter relevant fields and define which fields are relevant for each auth type

        auth_type = config_copy.get("auth", {}).get("type", "none")

        relevant_fields_by_type = {
            "token": {"api_key"},
            "bearer": {"access_token", "refresh_token", "token_type", "expires_at"},
            "basic": {"username", "password"},
            "custom": {"header_name", "header_value"},
        }

        # Define which fields are sensitive (should be masked)
        sensitive_fields = {"api_key", "access_token", "refresh_token", "password", "header_value"}

        # Get relevant fields for this auth type
        relevant_fields = relevant_fields_by_type.get(auth_type, set())

        masked_credentials = {}
        for key, value in decrypted.items():
            if key in relevant_fields and value is not None:
                if key in sensitive_fields:
                    masked_credentials[key] = "***ENCRYPTED***"
                else:
                    masked_credentials[key] = value

        config_copy["auth"]["credentials"] = masked_credentials

    return config_copy
