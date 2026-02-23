# Documentation Directory

This directory contains all documentation for the IoC CFN Management Backend Service.

## Directory Structure

```
docs/
├── README.md           # This file - documentation index
└── openapi/            # OpenAPI specification files
    └── openapi.json    # Generated OpenAPI 3.1.0 spec
```

## Documentation Contents

### OpenAPI Specification (`openapi/`)

Contains the generated OpenAPI/Swagger specification files:

- **openapi.json** - Auto-generated OpenAPI 3.1.0 specification
- Generated from FastAPI application schema
- Used by Swagger UI, ReDoc, Postman, and other API tools

## Generating Documentation

### Generate OpenAPI Spec

```bash
task generate-openapi-spec
```

This will regenerate `openapi/openapi.json` based on the current API implementation.

## Viewing API Documentation

Once the application is running, view the interactive API documentation at:

- **Swagger UI**: http://localhost:9000/api/docs
- **ReDoc**: http://localhost:9000/api/redoc
- **OpenAPI JSON**: http://localhost:9000/api/openapi.json

## Using the OpenAPI Spec

The `openapi/openapi.json` file can be used with:

- **Swagger UI** - Interactive API documentation
- **Postman** - Import spec to generate API requests
- **OpenAPI Generator** - Generate client SDKs
- **API testing tools** - Automated API testing

### Import into Postman

1. Open Postman
2. Click "Import"
3. Choose "Link" tab
4. Paste: `http://localhost:9000/api/openapi.json`
5. Click "Import"

## Additional Documentation

See also:

- [Contributing Guide](../CONTRIBUTING.md) - Development and contribution guidelines
- [Main README](../README.md) - Project overview and setup instructions
