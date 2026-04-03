# ioc-cfn-mgmt-plane

[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/orgs/cisco-eti/packages/container/package/ioc-cfn-mgmt-plane-svc)
[![GitHub Pages Site](https://img.shields.io/badge/GitHub%20Pages-Visit-green?logo=github)](https://scaling-potato-qm8j7n7.pages.github.io/)

IoC CFN Management Backend Service - FastAPI backend for workspaces, users, API keys, Cognitive Fabric Nodes, and Multi-Agentic Systems

## Prerequisites

- Python 3.10+
- Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- Make (usually pre-installed on Unix-like systems)

### Provide LLM Credentials

Provide the following env vars in env.conf:
- `LLM_MODEL` (e.g., `azure/gpt-4o`, `azure/gpt-4`, `gpt-4`)
- `LLM_API_KEY` (Your Azure OpenAI or OpenAI API key)
- `LLM_BASE_URL` (e.g., `https://your-resource.openai.azure.com/`)
- `AZURE_API_VERSION` (e.g., `2025-01-01-preview`) // optional for Azure OpenAI

### Dependencies for the Relational DB

For details please refer to the [README](src/server/database/relational_db/README.md)

- [PostgreSQL 17 Alpine](https://hub.docker.com/_/postgres)
- [Atlas](https://atlasgo.io/guides/orms/sqlalchemy/getting-started)

## Architecture

### Services

The full stack deployment includes the following services:

| Service | Port | Purpose |
|---------|------|---------|
| **ioc-cfn-mgmt-backend-svc** | 9000 | Management plane backend API |
| **ioc-cognition-fabric-node-svc** | 9002 | CFN service with embedded cognitive agents |
| **ioc-cfn-cognition-engine** | 9004 | Cognitive agents (ingestion, evidence, semantic negotiation, caching) |
| **ioc-knowledge-memory-svc** | 9003 | Knowledge graph + vector memory storage |
| **ioc-knowledge-db** | 5456 | PostgreSQL with AgensGraph + PgVector extensions |
| **ioc-mgmt-relational-db** | 5433 | PostgreSQL for management data |

### Service Flow

```
Client/API → Management Backend (9000)
                ↓
              CFN Service (9002)
                ↓
           Cognition Engine (9004) → Knowledge Memory (9003)
                                         ↓
                                     Knowledge DB (5456)
```

## Quick Start

### Deployment Options

**Option 1: I have deployed sql DB locally**

```bash
make run    # installs deps, applies db migrations, then runs
```

**Option 2: I don't have any db**

```bash
make docker-compose-db-up    # Start only databases (PostgreSQL) with db-only profile
make run                     # installs deps, applies db migrations, then runs
```

**Option 3: Full stack deployment**

```bash
make docker-compose-full-stack-up    # Start complete stack with all services
```

### Alternative Quick Start Methods

**Manual setup (if you have Poetry/Make already)**

```bash
poetry install
make dev
```

**API Documentation:** http://localhost:9000/docs

### Encryption Keys

Memory provider credentials are encrypted using a Fernet key. The key is automatically generated on first run and stored in `.secrets/encryption.key` (gitignored). Each developer gets a unique key.

## Development

**Using Make**

```bash
make dev              # Start development server
make test             # Run all tests
make docker-build     # Build Docker image
make docker-run       # Run Docker container
make help             # Show all available targets
```

**Using Poetry directly**

```bash
cd src
poetry run python -m server.main
```

**Using Docker**

```bash
make docker-compose-full-stack-up    # Full stack (mgmt-backend + cfn-svc + cognition-engine + knowledge-memory + databases)
make docker-compose-db-up            # Databases only
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
