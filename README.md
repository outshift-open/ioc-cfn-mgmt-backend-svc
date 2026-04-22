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

### GitHub Container Registry Authentication (for Full Stack deployment)

To pull Docker images from GitHub Container Registry (GHCR):

1. Go to https://github.com/settings/tokens
2. Create a new token with `read:packages` scope (or ensure existing token has this scope)
3. Click "Configure SSO" beside delete button
4. Authorize the token for cisco-eti organization
5. Login to Docker:

```bash
export GITHUB_TOKEN="xxxxxxxxxxxxx"  # replace with your token
echo "$GITHUB_TOKEN" | docker login ghcr.io -u "YOUR_GITHUB_USERNAME" --password-stdin
```

### Environment Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` to set your configuration values:

```bash
vi .env  # or use your preferred editor
```

### Provide LLM Credentials

Provide the following env vars in `.env`:
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

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

Run the full stack (UI + Backend + DB + CFN Service) using docker-compose:

```bash
# Edit .env to set your configuration values (IMAGE_TAG, credentials, etc.)

# Start services (pulls latest images)
task docker-compose-full-stack-up

# Stop services (preserves volumes)
task docker-compose-full-stack-down

# Stop services and remove volumes
task docker-compose-full-stack-down-with-volumes
```

> **Note:** The full-stack profile includes `ioc-cfn-svc` (port 9002), which now depends on
> `ioc-knowledge-db` (PostgreSQL), `ioc-cfn-mgmt-plane-svc`,
> and `ioc-knowledge-memory-svc`. Startup is gated on all services being healthy.
> The service shares database credentials (`IOC_KNOWLEDGE_DB_USER`, `IOC_KNOWLEDGE_DB_PASSWORD`)
> from `.env`.
>
> LLM integration requires the following environment variables to be set:
> `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `.env`.

### Alternative Quick Start Methods

**Manual setup (if you have Poetry/Task already)**

```bash
poetry install
task dev
```

**API Documentation:** http://localhost:9000/docs

### Encryption Keys

Memory provider credentials are encrypted using a Fernet key. The key is automatically generated on first run and stored in `.secrets/encryption.key` (gitignored). Each developer gets a unique key.

## Service Endpoints

Once all services are running (full-stack deployment), access them at:

- **IoC Management UI**: http://localhost:9001 (username and password are defined in `.env`)
- **IoC Management API**: http://localhost:9000/docs
- **CFN Service**: http://localhost:9002
- **Knowledge Memory Service**: http://localhost:9003
- **AgensGraph Database**: localhost:5456
- **AgensGraph Viewer**: http://localhost:5457
- **Cognition Engine - Reasoning and Evidence Gathering**: Port 9004
- **Cognition Engine - Semantic Negotiation**: Port 9004

To enable these services, uncomment their definitions in docker-compose.yml.

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
