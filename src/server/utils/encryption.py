# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Encryption utilities for sensitive data"""

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

from server.utils.repo_root import REPO_ROOT

logger = logging.getLogger(__name__)

# Path to encryption key file
ENCRYPTION_KEY_FILE = Path(REPO_ROOT) / ".secrets" / "encryption.key"


def _load_or_generate_encryption_key() -> Optional[str]:
    """
    Load encryption key from file or environment, or generate a new one.

    Priority:
    1. Environment variable MEMORY_PROVIDER_ENCRYPTION_KEY (for Docker/production)
    2. File at .secrets/encryption.key (auto-generated for local dev)
    3. Generate new key and save to file

    Returns:
        Encryption key as string, or None if generation fails
    """
    # Check environment variable first (for Docker)
    env_key = os.getenv("MEMORY_PROVIDER_ENCRYPTION_KEY")
    if env_key:
        logger.info("Using encryption key from environment variable")
        return env_key

    # Check if key file exists
    if ENCRYPTION_KEY_FILE.exists():
        try:
            key = ENCRYPTION_KEY_FILE.read_text().strip()
            logger.info(f"Loaded encryption key from {ENCRYPTION_KEY_FILE}")
            return key
        except Exception as e:
            logger.error(f"Failed to read encryption key from {ENCRYPTION_KEY_FILE}: {e}")
            return None

    # Generate new key
    try:
        logger.info("No encryption key found - generating new key")
        new_key = Fernet.generate_key().decode()

        # Create .secrets directory if it doesn't exist
        ENCRYPTION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Save key to file
        ENCRYPTION_KEY_FILE.write_text(new_key)

        # Set restrictive permissions (owner read/write only)
        ENCRYPTION_KEY_FILE.chmod(0o600)

        logger.info(f"Generated and saved new encryption key to {ENCRYPTION_KEY_FILE}")
        return new_key
    except Exception as e:
        logger.error(f"Failed to generate encryption key: {e}")
        return None


# Load or generate encryption key
ENCRYPTION_KEY = _load_or_generate_encryption_key()
if not ENCRYPTION_KEY:
    logger.warning("Encryption key not available - credentials will not be encrypted")
    cipher = None
else:
    cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_credentials(credentials: dict) -> Optional[str]:
    """
    Encrypt credentials dictionary to encrypted string

    Args:
        credentials: Dict with sensitive fields like api_key, password, etc.

    Returns:
        Base64-encoded encrypted string or None if no cipher
    """
    if not cipher:
        logger.warning("Encryption key not configured - storing credentials in plaintext")
        return None

    if not credentials:
        return None

    try:
        # Serialize to JSON
        json_bytes = json.dumps(credentials).encode("utf-8")

        # Encrypt
        encrypted_bytes = cipher.encrypt(json_bytes)

        # Return as string for JSONB storage
        return encrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encrypt credentials: {e}")
        raise


def decrypt_credentials(encrypted: str) -> dict:
    """
    Decrypt encrypted credentials string to dictionary

    Args:
        encrypted: Base64-encoded encrypted string

    Returns:
        Decrypted credentials dictionary
    """
    if not cipher:
        logger.warning("Encryption key not configured - cannot decrypt")
        return {}

    if not encrypted:
        return {}

    try:
        # Decrypt
        encrypted_bytes = encrypted.encode("utf-8")
        decrypted_bytes = cipher.decrypt(encrypted_bytes)

        # Parse JSON
        credentials = json.loads(decrypted_bytes.decode("utf-8"))

        return credentials
    except Exception as e:
        logger.error(f"Failed to decrypt credentials: {e}")
        raise


def process_config_for_storage(config: dict) -> dict:
    """
    Process config before storing in database - encrypt credentials

    Args:
        config: Memory provider config dict

    Returns:
        Config with credentials encrypted
    """
    config_copy = config.copy()

    # Check if auth has credentials
    if config_copy.get("auth", {}).get("type") != "none":
        credentials = config_copy.get("auth", {}).get("credentials")

        if credentials:
            # Encrypt credentials
            encrypted = encrypt_credentials(credentials)

            if encrypted:
                config_copy["auth"]["credentials_encrypted"] = encrypted
                del config_copy["auth"]["credentials"]

    return config_copy


def process_config_for_cfn(config: dict) -> dict:
    """
    Process config before sending to CFN - decrypt credentials

    Args:
        config: Memory provider config dict from database

    Returns:
        Config with credentials decrypted
    """
    config_copy = config.copy()

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
    Process config before returning in API response - mask sensitive credentials.
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
