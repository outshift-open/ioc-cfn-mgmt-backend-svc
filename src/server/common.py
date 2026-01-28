import os
import json
import logging
from cryptography.fernet import Fernet

# Get logger instance (logging is setup in main.py)
logger = logging.getLogger(__name__)

service_name = os.environ.get("SERVICE_NAME", "ioc-cfn-mgmt-backend")


def get_global_encryption_key() -> bytes:
    """Load and decode the base64-encoded DEK from config file"""
    try:
        # Look for config.json in the same directory as this file (src/server/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "config.json")

        with open(config_path) as f:
            config = json.load(f)

        dek = config.get("DEK", "")
        if not dek:
            raise ValueError("DEK not found in config file")

        # The key should be a URL-safe base64-encoded string
        # Pad with '=' to make the length a multiple of 4 if needed
        key = dek
        key += "=" * (-len(key) % 4)

        # Convert to bytes and return
        return key.encode("utf-8")

    except Exception as e:
        logger.error(f"Reading Data encryption key failed: {e}")
        raise


def encrypt_data(data: str, key: bytes) -> str:
    """Encrypt data using the provided key"""
    try:
        f = Fernet(key)
        encrypted = f.encrypt(data.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Data encryption failed: {e}")
        raise


def decrypt_data(encrypted_data: str, key: bytes) -> str:
    """Decrypt data using the provided key"""
    try:
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Data decryption failed: {e}")
        raise
