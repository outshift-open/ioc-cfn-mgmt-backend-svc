# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Validation utilities for API inputs"""

import uuid
from fastapi import HTTPException, status


def validate_uuid(uuid_string: str, field_name: str = "ID") -> str:
    """Validate that a string is a valid UUID format

    Args:
        uuid_string: The string to validate
        field_name: Name of the field for error messages

    Returns:
        The validated UUID string

    Raises:
        HTTPException: If UUID format is invalid
    """
    try:
        uuid.UUID(uuid_string)
        return uuid_string
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Must be a valid UUID.",
        )
