# ioc-cfn-mgmt-backend

TKF Data Logic Service - FastAPI workspace, user, and API key management

## Prerequisites

- Python 3.8+
- Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- Task:
  - **macOS**: `brew install go-task`
  - **Linux**: `apt install task`, `dnf install go-task`, or `snap install task --classic`
  - **Cross-platform**: `npm install -g @go-task/cli`
  - **Go users**: `go install github.com/go-task/task/v3/cmd/task@latest`
  - **Manual install**: `sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin`
  - **All-in-one setup**: `./install.sh` (installs Poetry and Task globally, and dependencies)

#### Dependencies for the Relational DB
For details please refer to the [README](src/server/database/relational_db/README.md)
- [TimescaleDB(Postgres17)](https://www.tigerdata.com/docs/self-hosted/latest/install/installation-docker)
- [Atlas](https://atlasgo.io/guides/orms/sqlalchemy/getting-started)

## Quick Start

### Deployment Options

**Option 1: I have deployed neo4j and sql DB locally**

```bash
task run    # installs deps, applies db migrations, generates DEK, then runs
```

**Option 2: I don't have any db**

```bash
task docker-compose-db-up    # Start only databases (PostgreSQL and Neo4j) with db-only profile
task run                     # installs deps, applies db migrations, generates DEK, then runs
```

**Option 3: Full stack deployment**

```bash
task docker-compose-up       # Start complete stack (application + databases)
```

### Alternative Quick Start Methods

**Dev setup (installs Poetry and Task globally)**

```bash
./install.sh
task dev
```

**Manual setup (if you have Poetry/Task already)**

```bash
poetry install
task dev
```

**API Documentation:** http://localhost:8000/docs

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
cd src/server
poetry run python main.py
```

**Using Docker**

```bash
docker-compose up --build
```

## API Endpoints

- **Workspaces:** `GET|POST|PUT|DELETE /api/workspaces`
- **Users:** `GET|POST|DELETE /api/workspaces/{workspace_id}/users`
- **API Keys:** `GET|POST|DELETE /api/workspaces/{workspace_id}/api-keys`
