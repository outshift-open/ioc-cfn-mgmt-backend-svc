# Contributing to ioc-cfn-mgmt-backend

Thank you for your interest in contributing to the IOC CFN Management Backend Service!

## General Guidelines

- For pushing git tags/branches to this repo, please reach out to [IOC team](mailto:ccs-dev-team@cisco.com)

## Development Setup

### Prerequisites

- Python 3.10+
- Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- Task (go-task): See [README.md](README.md#prerequisites) for installation options
- PostgreSQL 17 with TimescaleDB (or use Docker Compose)

### Getting Started

```bash
# Clone the repository
git clone <repository-url>
cd ioc-cfn-mgmt-backend-svc

# Start databases
task docker-compose-db-up

# Install dependencies and run migrations
task run  # Installs deps, applies migrations, runs server

# Or for development with hot reload
task dev
```

## Coding Conventions

### Naming Conventions

**File Naming:**
- ✅ Use full descriptive names, not abbreviations
- ✅ Good: `cognitive_fabric_node.py`, `multi_agentic_system.py`
- ❌ Avoid: `cfn.py`, `mas.py`

**Class Naming:**
- ✅ Use full descriptive names with PascalCase
- ✅ Good: `CognitiveFabricNodeService`, `WorkspaceService`
- ❌ Avoid: `CFNService`, `WSService`

**Service Method Naming:**
- ✅ Simple action verbs (class name provides context)
- ✅ Good: `register()`, `update()`, `deregister()`, `get()`, `list()`
- ❌ Avoid: `register_cognitive_fabric_node()`, `get_cfn()`

**API Field Naming:**
- API fields may use abbreviations (e.g., `cfn_id`, `mas_id`) for brevity
- This is part of the API contract and acceptable for backward compatibility

### Service Patterns

**Service Singletons:**
```python
# In service file (e.g., cognitive_fabric_node.py)
class CognitiveFabricNodeService:
    def register(self, workspace_id, data, user_id):
        pass

# Singleton instance at bottom of file
cognitive_fabric_node_service = CognitiveFabricNodeService()
```

**Service Exports:**
```python
# In services/__init__.py
from .cognitive_fabric_node import cognitive_fabric_node_service, CognitiveFabricNodeService
```

## Testing

### Running Tests

```bash
# Run all tests
task test

# Run specific test file
poetry run pytest tests/test_cognitive_fabric_node.py -v

# Run with coverage
task test-coverage
```

### Test Database

Tests use a separate `tkf_test` database. The test fixtures automatically:
- Create necessary tables
- Clean up data after each test
- Use pytest-asyncio for async support

### Test Conventions

- DELETE endpoints return 204 (No Content) status code on success, not 200
- API POST (Create) returns 201 Created with resource in response body
- API GET (Read) returns 200 OK with resource(s)
- API PUT (Update) returns 200 OK with updated resource
- API DELETE returns 204 No Content (no response body)

## Database Migrations

### Creating Migrations

```bash
# Create a new migration
task db-migrate-new -- "description_of_changes"

# Apply migrations
task db-migrate-apply

# Check migration status
task db-migrate-status
```

### Migration Guidelines

- Use Atlas for all schema changes
- Migrations are stored in `src/server/database/relational_db/migrations/`
- Always test migrations locally before committing
- Include both up and down migration paths

## Pull Request Process

1. **Create a feature branch** from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following coding conventions

3. **Write/update tests** for your changes
   ```bash
   task test
   ```

4. **Run linting**
   ```bash
   task lint-check  # Check only
   task lint        # Fix issues
   ```

5. **Commit your changes**
   ```bash
   git add <files>
   git commit -m "Description of changes"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **PR Requirements:**
   - All tests must pass
   - Code must follow naming conventions
   - Include migration files if schema changes
   - Update documentation (README, CLAUDE.md) if needed

## Common Tasks

```bash
task dev                    # Start dev server with hot reload
task test                   # Run all tests
task lint                   # Fix linting issues
task docker-build           # Build Docker image
task docker-compose-db-up   # Start databases only
task db-migrate-apply       # Apply database migrations
```

For a complete list of available tasks:
```bash
task --list
```

## Architecture Notes

### Service Structure

- **Workspaces**: Top-level tenant isolation
- **Users**: Belong to workspaces via `workspace_member` table
- **API Keys**: User-scoped (not workspace-scoped) for flexibility
- **CFN Nodes**: Workspace-scoped resources
- **Multi-Agentic Systems**: Workspace-scoped resources

### Authorization

- API keys identify users (via `X-API-Key` header)
- Workspace access determined by membership in `workspace_member` table
- Only workspace admins and creators can list/manage workspaces
- `super_admin` role has global access (future feature)

## Getting Help

- Review [CLAUDE.md](CLAUDE.md) for detailed architecture documentation
- Check the [README.md](README.md) for quick start guides
- Reach out to the team via [eti-sre-admins@cisco.com](mailto:eti-sre-admins@cisco.com)
