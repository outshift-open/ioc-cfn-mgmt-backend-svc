#!/usr/bin/env python3

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""
Generate OpenAPI spec from FastAPI app and save to docs/openapi/openapi.json
"""

import json
import os
import sys
from pathlib import Path

from server.main import app

# Add the src directory to the path so we can import server modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def generate_openapi_spec():
    """Generate OpenAPI spec and save to docs/openapi/openapi.json"""

    # Get the openapi docs directory path
    repo_root = Path(__file__).parent.parent
    openapi_dir = repo_root / "docs" / "openapi"

    # Create openapi directory if it doesn't exist
    openapi_dir.mkdir(parents=True, exist_ok=True)

    # Generate OpenAPI spec
    openapi_spec = app.openapi()

    # Convert OpenAPI 3.1.0 to 3.0.0 for better Swagger UI compatibility
    if openapi_spec.get('openapi') == '3.1.0':
        openapi_spec['openapi'] = '3.0.0'

    # Save to file
    spec_file = openapi_dir / "openapi.json"

    with open(spec_file, 'w') as f:
        json.dump(openapi_spec, f, indent=2)

    print(f"✓ OpenAPI spec generated and saved to {spec_file}")
    return str(spec_file)


if __name__ == "__main__":
    try:
        generate_openapi_spec()
    except Exception as e:
        print(f"✗ Error generating OpenAPI spec: {e}", file=sys.stderr)
        sys.exit(1)
