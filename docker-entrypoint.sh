#!/bin/bash
set -e

echo "Starting application initialization..."
cd /home/app

# ---------------------------------------------------------------------------
# 1. Database migrations (Alembic)
# ---------------------------------------------------------------------------
echo "Running database migrations..."

DB_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

# One-time transition from the old bash migrate.sh runner to Alembic.
# If this database was previously managed by migrate.sh (has schema_migrations
# table) but has never seen Alembic (no alembic_version table), we stamp the
# current head revision so Alembic doesn't re-run migrations that already exist.
# This block is safe to leave permanently -- once stamped, the condition is false.
OLD_TRACKER=$(psql "$DB_URL" --no-psqlrc -tA -c \
  "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations');" 2>/dev/null || echo "f")
ALEMBIC_TRACKER=$(psql "$DB_URL" --no-psqlrc -tA -c \
  "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version');" 2>/dev/null || echo "f")

if [ "$OLD_TRACKER" = "t" ] && [ "$ALEMBIC_TRACKER" = "f" ]; then
    echo "  Migrating from bash runner to Alembic -- stamping revision 0008..."
    alembic stamp 0008
fi

alembic upgrade head
echo "  Migrations complete."

# ---------------------------------------------------------------------------
# 2. Seed data
# ---------------------------------------------------------------------------
SEED_FILE="/home/app/src/server/database/relational_db/scripts/populate_software.sql"
if [ -f "$SEED_FILE" ]; then
    echo "Seeding database..."
    psql "$DB_URL" -f "$SEED_FILE"
else
    echo "Warning: populate_software.sql not found, skipping seed."
fi

# ---------------------------------------------------------------------------
# 3. Start application
# ---------------------------------------------------------------------------
echo "Starting application server..."
exec uvicorn server.main:app --host 0.0.0.0 --port 9000