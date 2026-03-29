# ioc-cfn-mgmt-plane

[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/orgs/cisco-eti/packages/container/package/ioc-cfn-mgmt-plane-svc)
[![GitHub Pages Site](https://img.shields.io/badge/GitHub%20Pages-Visit-green?logo=github)](https://scaling-potato-qm8j7n7.pages.github.io/)

IoC CFN Management Backend Service - FastAPI backend for workspaces, users, API keys, Cognitive Fabric Nodes, and Multi-Agentic Systems

## Prerequisites

- Python 3.10+
- Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- Task:
  - **macOS**: `brew install go-task`
  - **Linux**: `apt install task`, `dnf install go-task`, or `snap install task --classic`
  - **Cross-platform**: `npm install -g @go-task/cli`
  - **Go users**: `go install github.com/go-task/task/v3/cmd/task@latest`
  - **Manual install**: `sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin`

### Provide LLM Credentials

Provide the following env vars in env.conf:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION` // optional, remove if not needed

### Dependencies for the Relational DB

For details please refer to the [README](src/server/database/relational_db/README.md)

- [PostgreSQL 17 Alpine](https://hub.docker.com/_/postgres)
- [Atlas](https://atlasgo.io/guides/orms/sqlalchemy/getting-started)

## Quick Start

### Deployment Options

**Option 1: I have deployed sql DB locally**

```bash
task run    # installs deps, applies db migrations, then runs
```

**Option 2: I don't have any db**

```bash
task docker-compose-db-up    # Start only databases (PostgreSQL) with db-only profile
task run                     # installs deps, applies db migrations, then runs
```

**Option 3: Full stack deployment**

```bash
task docker-compose-full-stack-up    # Start complete stack (application + databases + cfn-svc)
```

### Alternative Quick Start Methods

**Manual setup (if you have Poetry/Task already)**

```bash
poetry install
task dev
```

**API Documentation:** http://localhost:9000/docs

### Encryption Keys

Memory provider credentials are encrypted using a Fernet key. The key is automatically generated on first run and stored in `.secrets/encryption.key` (gitignored). Each developer gets a unique key.

## Development

**Using Task**

```bash
task dev              # Start development server
task test             # Run all tests
task docker-build     # Build Docker image
task docker-run       # Run Docker container
```

**Using Poetry directly**

```bash
cd src
poetry run python -m server.main
```

**Using Docker**

```bash
task docker-compose-full-stack-up    # Full stack (mgmt-backend + cfn-svc + ui + databases)
task docker-compose-db-up            # Databases only
```

## API Endpoints

**API Documentation:** http://localhost:9000/docs

**IAM (Identity and Access Management):**

- API Keys: `GET|POST|DELETE /api/iam/api-keys`
- Users: `GET /api/iam/users`
- Roles: `GET /api/iam/roles`

**Workspaces:**

- Workspaces: `GET|POST|PUT|DELETE /api/workspaces`
- Workspace Members: `GET|POST|DELETE /api/workspaces/{workspace_id}/members`
- Workspace Invitations: `GET|POST|DELETE /api/workspaces/{workspace_id}/invitations`

**Workspace Resources:**

- Multi-Agentic Systems: `GET|POST|DELETE /api/workspaces/{workspace_id}/multi-agentic-systems`
- Cognitive Fabric Nodes: `GET|POST|PUT|DELETE /api/workspaces/{workspace_id}/cognitive-fabric-node`

**CFN Audit Events** (from `cfn_cp` database):
- List all events: `GET /api/audit-events`
- Filter events: `GET /api/audit-events?resource_type=MAS&audit_type=RESOURCE_CREATED`
- Get event by ID: `GET /api/audit-events/{id}`

```bash
# List all CFN audit events
curl http://localhost:9000/api/audit-events/

# Filter by resource_type and audit_type
curl "http://localhost:9000/api/audit-events/?resource_type=MAS&audit_type=RESOURCE_CREATED"

# Get a specific audit event by UUID
curl http://localhost:9000/api/audit-events/5bda66e6-1608-4f83-b7e4-aadbddce312c
```

**Other:**

- Audit Logs: `GET /api/audits`
