# API Documentation

This directory contains the OpenAPI/Swagger specification for the IOC CFN Management Backend Service API.

## Generated Files

- `openapi.json` - The generated OpenAPI 3.1.0 specification for the API

## Generating the OpenAPI Spec

To generate or regenerate the OpenAPI specification, run:

```bash
task generate-openapi-spec
```

This will create/update the `openapi.json` file with the latest API schema based on the current FastAPI application configuration.

## Viewing the API Documentation

Once the application is running, you can view the interactive API documentation at:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

## Using the OpenAPI Spec

The `openapi.json` file can be used with various tools:

- **Swagger UI** - View interactive API docs
- **Postman** - Import the spec to generate API requests
- **OpenAPI Generator** - Generate client SDKs in various languages
- **API documentation tools** - Generate API docs in different formats

### Example: Import into Postman

1. Open Postman
2. Click "Import"
3. Choose "Link" tab
4. Paste: `http://localhost:8000/api/openapi.json` (when running locally)
5. Click "Import"
