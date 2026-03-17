# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Repository root path utilities."""

import os


def get_repo_root() -> str:
    """Get the repository root path by locating pyproject.toml.

    Returns:
        str: Absolute path to the repository root

    Raises:
        RuntimeError: If pyproject.toml is not found in the directory tree
    """
    current = os.path.dirname(os.path.abspath(__file__))
    while current != os.path.dirname(current):  # Stop at filesystem root
        if os.path.exists(os.path.join(current, "pyproject.toml")):
            return current
        current = os.path.dirname(current)
    raise RuntimeError("Could not find repository root (pyproject.toml not found)")


# Module-level constant for repository root
REPO_ROOT = get_repo_root()
