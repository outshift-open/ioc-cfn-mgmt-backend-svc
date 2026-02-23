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

> **Note:** The full-stack profile includes `ioc-cfn-svc` (port 9002), which depends on both
> `ioc-cfn-mgmt-plane-svc` and PostgreSQL. It shares database credentials
> (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`) from `env.conf` and uses a
> separate database (`DB_NAME=cfn_cp`).

### Alternative Quick Start Methods

**Manual setup (if you have Poetry/Task already)**

```bash
poetry install
task dev
```

**API Documentation:** http://localhost:9000/docs

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

**Other:**
- Audit Logs: `GET /api/audits`
