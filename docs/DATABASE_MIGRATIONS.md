# Database Migrations Guide

> **TL;DR** — Edit a model, run one command to generate the migration, commit it. Done.
> The migration applies automatically when the container restarts.

---

## 4 Commands You Need

```bash
task db-migrate-apply                          # Apply pending migrations to your local DB
task db-migrate-status                         # See what's applied and what's pending
task db-migrate-revision -- "your message"     # Generate a new migration from model changes
task db-migrate-downgrade                      # Undo the last migration
```

That's it. Everything else is automatic.

---

## Step-by-Step: Making a Schema Change

Here's the full workflow for adding a `foo` column to the `workspace` table.

### Step 1 — Edit the SQLAlchemy model

```python
# src/server/database/relational_db/models/workspace.py

from sqlalchemy import Column, String
# ... other imports ...

class Workspace(Base):
    __tablename__ = "workspace"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    # ... other existing columns ...

    foo = Column(String(100), nullable=True)    # <-- ADD THIS LINE
```

### Step 2 — Make sure your local DB is running

```bash
task docker-compose-db-up
```

### Step 3 — Generate the migration

```bash
task db-migrate-revision -- "add foo to workspace"
```

You'll see output like:
```
Detected added column 'workspace.foo'
Generating alembic/versions/c103410d7e70_add_foo_to_workspace.py ... done
```

### Step 4 — Open the generated file and review it

The file will be at `alembic/versions/<hash>_add_foo_to_workspace.py`.

**Important:** Autogenerate sometimes detects unrelated differences between models and the database. Delete anything that isn't your change. You should end up with:

```python
"""add foo to workspace"""
from alembic import op
import sqlalchemy as sa

revision = "c103410d7e70"
down_revision = "0008"       # points to the previous migration


def upgrade() -> None:
    op.add_column("workspace", sa.Column("foo", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace", "foo")
```

### Step 5 — Apply it locally to test

```bash
task db-migrate-apply
```

Output:
```
Running upgrade 0008 -> c103410d7e70, add foo to workspace
```

### Step 6 — Verify it worked

```bash
task db-migrate-status
```

### Step 7 — Commit and push

```bash
git add src/server/database/relational_db/models/workspace.py
git add alembic/versions/c103410d7e70_add_foo_to_workspace.py
git commit -m "feat: add foo column to workspace"
git push
```

### Step 8 — Deploy

When the new image deploys, the container runs `alembic upgrade head` on startup. It detects the pending migration, applies it, and the app starts. The database stays up the entire time — zero downtime.

---

## What Happens on Deploy (Automatically)

```
Container starts
    │
    ▼
docker-entrypoint.sh runs:
    │
    │  1. alembic upgrade head
    │     └─ Checks current DB revision (e.g., 0008)
    │     └─ Sees new migration (e.g., c103410d7e70)
    │     └─ Applies it in a single transaction
    │     └─ Updates alembic_version table
    │
    │  2. Seed data (if populate_software.sql exists)
    │
    │  3. uvicorn starts
    ▼
App is serving traffic
```

**If the pod crashes during step 1:** PostgreSQL rolls back the transaction. Nothing was applied. Next restart retries cleanly.

**If the DB is already up to date:** `alembic upgrade head` does nothing (prints "No pending migrations") and the app starts immediately.

---

## Rolling Back a Bad Migration

### Undo the last migration

```bash
task db-migrate-downgrade
```

This runs the `downgrade()` function from the most recent migration (e.g., drops the column you just added).

### Undo multiple migrations

```bash
# Go back to revision 0006
PYTHONPATH=src poetry run alembic downgrade 0006
```

---

## Common Recipes

### Add a nullable column

```python
def upgrade():
    op.add_column("workspace", sa.Column("icon", sa.String(255), nullable=True))

def downgrade():
    op.drop_column("workspace", "icon")
```

### Add a required column (NOT NULL with default)

```python
def upgrade():
    op.add_column("workspace", sa.Column("status", sa.String(50), nullable=False, server_default="active"))

def downgrade():
    op.drop_column("workspace", "status")
```

### Create a new table

```python
def upgrade():
    op.create_table(
        "tag",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("idx_tag_workspace_id", "tag", ["workspace_id"])

def downgrade():
    op.drop_index("idx_tag_workspace_id", table_name="tag")
    op.drop_table("tag")
```

### Add an index

```python
def upgrade():
    op.create_index("idx_audit_created_at", "audit", ["created_at"])

def downgrade():
    op.drop_index("idx_audit_created_at", table_name="audit")
```

### Rename a column

```python
def upgrade():
    op.alter_column("workspace", "config", new_column_name="settings")

def downgrade():
    op.alter_column("workspace", "settings", new_column_name="config")
```

### Run raw SQL

```python
def upgrade():
    op.execute("UPDATE workspace SET status = 'active' WHERE status IS NULL")
```

---

## Rules to Follow

1. **Always review autogenerated migrations.** Delete anything that isn't your intended change.
2. **Always write a `downgrade()`.** It should exactly reverse the `upgrade()`.
3. **Never edit a migration that's already been deployed.** Create a new migration instead.
4. **One logical change per migration.** "Add icon column" is one migration. "Add icon + rename config + create tag table" should be 2-3 separate migrations.
5. **Test locally before pushing.** Run `task db-migrate-apply` and verify with `task db-migrate-status`.

---

## Troubleshooting

| You see this | Do this |
|---|---|
| `Target database is not up to date` | `task db-migrate-apply` |
| `Multiple heads detected` | Two people created migrations from same parent. Run: `PYTHONPATH=src poetry run alembic merge heads -m "merge"` |
| `relation "X" already exists` | Your migration is missing `IF NOT EXISTS`, or DB is ahead of Alembic's tracking. Check with `task db-migrate-status` |
| Pod crashed mid-migration | Nothing to do. PostgreSQL auto-rolled-back. Next restart retries. |
| Need to check what revision the DB is on | `task db-migrate-status` (locally) or check `alembic_version` table in the DB |

---

## Environment Variables

Alembic reads the same env vars as the app (loaded from `env.conf` locally):

| Variable | Default | Used for |
|----------|---------|----------|
| `POSTGRES_HOST` | `localhost` | Where the DB is |
| `POSTGRES_PORT` | `5432` | DB port (use `5456` locally since docker maps to that) |
| `POSTGRES_USER` | `postgresUser` | DB credentials |
| `POSTGRES_PASSWORD` | `postgresPW` | DB credentials |
| `POSTGRES_DB` | `cfn_mgmt` | Which database to migrate |

---

## File Layout

```
project root/
├── alembic.ini                          # Points to alembic/ directory
├── alembic/
│   ├── env.py                           # Connects to DB, imports all models
│   ├── script.py.mako                   # Template for new migration files
│   └── versions/                        # All migration files live here
│       ├── 0001_consolidated_schema.py
│       ├── 0002_add_workspace_scoped_agents_and_policies.py
│       ├── ...
│       └── 0008_add_description_to_memory_provider.py
└── src/server/database/relational_db/
    └── models/                          # SQLAlchemy models (source of truth)
        ├── __init__.py                  # Base = declarative_base()
        ├── workspace.py
        ├── user.py
        └── ...
```