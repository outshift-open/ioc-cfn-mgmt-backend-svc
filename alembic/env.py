"""
Alembic environment configuration.

Connects to the same Postgres database as the application using the standard
POSTGRES_* environment variables (with the same defaults as db.py).

All SQLAlchemy models are imported so that `alembic revision --autogenerate`
can diff the models against the live database schema.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Model metadata (needed for --autogenerate)
# ---------------------------------------------------------------------------
from server.database.relational_db.models import Base

# Each import registers that model's tables on Base.metadata.
import server.database.relational_db.models.agent  # noqa: F401
import server.database.relational_db.models.api_key  # noqa: F401
import server.database.relational_db.models.cognition_fabric_node  # noqa: F401
import server.database.relational_db.models.cognition_engine  # noqa: F401
import server.database.relational_db.models.memory_provider  # noqa: F401
import server.database.relational_db.models.multi_agentic_system  # noqa: F401
import server.database.relational_db.models.policies  # noqa: F401
import server.database.relational_db.models.user  # noqa: F401
import server.database.relational_db.models.workspace  # noqa: F401
import server.database.relational_db.models.workspace_invitation  # noqa: F401
import server.database.relational_db.models.workspace_member  # noqa: F401

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Alembic config & logging
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ---------------------------------------------------------------------------
# Database URL
# ---------------------------------------------------------------------------
def get_url() -> str:
    """
    Build the database URL from environment variables.

    Priority:
      1. ALEMBIC_DB_URL  (explicit override, useful for CI/testing)
      2. POSTGRES_* vars  (same env vars and defaults used by the app's db.py)
    """
    override = os.environ.get("ALEMBIC_DB_URL")
    if override:
        return override

    user = os.environ.get("POSTGRES_USER", "postgresUser")
    password = os.environ.get("POSTGRES_PASSWORD", "postgresPW")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "cfn_mgmt")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Generate SQL scripts without a live database connection."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()