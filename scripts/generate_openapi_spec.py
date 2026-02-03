#!/usr/bin/env python3
"""
Generate OpenAPI spec from FastAPI app and save to docs/openapi.json
"""

import json
import os
import sys
from pathlib import Path

from server.main import app

# Add the src directory to the path so we can import server modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def generate_openapi_spec():
    """Generate OpenAPI spec and save to docs/openapi.json"""

    # Get the docs directory path
    repo_root = Path(__file__).parent.parent
    docs_dir = repo_root / "docs"

    # Create docs directory if it doesn't exist
    docs_dir.mkdir(exist_ok=True)

    # Generate OpenAPI spec
    openapi_spec = app.openapi()

    # Save to file
    spec_file = docs_dir / "openapi.json"

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
