# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Version management utilities."""

import os

import tomllib

from .repo_root import REPO_ROOT


def get_app_version() -> str:
    """Get version from pyproject.toml or environment variable.

    Returns:
        str: Application version from environment variable, pyproject.toml, or default "0.0.0"
    """
    # First try to get from environment variable
    env_version = os.environ.get("APPLICATION_VERSION")
    if env_version:
        return env_version

    # Fall back to reading from pyproject.toml
    try:
        pyproject_path = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        return "0.0.0"
