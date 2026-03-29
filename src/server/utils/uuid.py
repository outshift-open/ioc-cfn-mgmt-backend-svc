# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""UUID generation utility

This module provides a centralized UUID generation function for the application.
All UUID generation should go through this utility to ensure consistency.
"""

import uuid


def generate_uuid() -> str:
    """
    Generate a new UUID string.

    Returns:
        str: A UUID4 string representation (36 characters with hyphens)

    Example:
        >>> uuid_str = generate_uuid()
        >>> print(uuid_str)
        '550e8400-e29b-41d4-a716-446655440000'
    """
    return str(uuid.uuid4())
