#!/bin/bash
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0
# ---------------------------------------------------------------------------
# Lightweight SQL migration runner (no external tools required)
# Uses a "schema_migrations" table to track applied migrations.
# Usage:
#   ./scripts/migrate.sh apply   — apply all pending migrations
#   ./scripts/migrate.sh status  — show applied / pending migrations
# ---------------------------------------------------------------------------
set -euo pipefail

echo "Using plain SQL migrations (no Atlas/HCL dependency)"

# ---------------------------------------------------------------------------
# Configuration (override via environment)
# ---------------------------------------------------------------------------
: "${POSTGRES_USER:=postgresUser}"
: "${POSTGRES_PASSWORD:=postgresPW}"
: "${POSTGRES_HOST:=localhost}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:=cfn_mgmt}"

DB_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

# Resolve the migrations directory relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-${SCRIPT_DIR}/../src/server/database/relational_db/migrations}"
MIGRATIONS_DIR="$(cd "$MIGRATIONS_DIR" && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
psql_exec() {
  psql "$DB_URL" --no-psqlrc --tuples-only --no-align -c "$1" 2>&1
}

psql_file() {
  psql "$DB_URL" --no-psqlrc --single-transaction -f "$1" 2>&1
}

ensure_tracking_table() {
  psql_exec "
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version  TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  " > /dev/null
}

is_applied() {
  local version="$1"
  local result
  result=$(psql_exec "SELECT 1 FROM schema_migrations WHERE version = '${version}' LIMIT 1;")
  [[ "$result" == "1" ]]
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
cmd_apply() {
  ensure_tracking_table

  local applied=0
  local skipped=0

  for file in "$MIGRATIONS_DIR"/*.sql; do
    [ -f "$file" ] || continue
    local filename
    filename="$(basename "$file")"

    if is_applied "$filename"; then
      skipped=$((skipped + 1))
      continue
    fi

    echo "  Applying: $filename ..."
    output=$(psql_file "$file") || {
      echo "  ✗ FAILED: $filename"
      echo "$output"
      exit 1
    }

    psql_exec "INSERT INTO schema_migrations (version) VALUES ('${filename}');" > /dev/null
    echo "  ✓ Applied: $filename"
    applied=$((applied + 1))
  done

  if [ "$applied" -eq 0 ]; then
    echo "  No pending migrations (${skipped} already applied)."
  else
    echo "  Done. Applied ${applied} migration(s), skipped ${skipped}."
  fi
}

cmd_status() {
  ensure_tracking_table

  echo ""
  echo "Migration Status"
  echo "================"

  for file in "$MIGRATIONS_DIR"/*.sql; do
    [ -f "$file" ] || continue
    local filename
    filename="$(basename "$file")"

    if is_applied "$filename"; then
      local ts
      ts=$(psql_exec "SELECT applied_at FROM schema_migrations WHERE version = '${filename}';")
      printf "  ✓  %-60s  %s\n" "$filename" "$ts"
    else
      printf "  ○  %-60s  %s\n" "$filename" "pending"
    fi
  done
  echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "${1:-}" in
  apply)
    echo "==> Applying database migrations..."
    cmd_apply
    ;;
  status)
    cmd_status
    ;;
  *)
    echo "Usage: $0 {apply|status}"
    echo ""
    echo "Commands:"
    echo "  apply   Apply all pending migrations in order"
    echo "  status  Show applied and pending migrations"
    exit 1
    ;;
esac
