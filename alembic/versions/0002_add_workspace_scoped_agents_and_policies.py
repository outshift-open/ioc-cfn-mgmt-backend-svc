"""add policies

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-19 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS "policy" (
      "id" character varying(36) NOT NULL,
      "workspace_id" character varying(36) NOT NULL,
      "name" character varying(255) NOT NULL,
      "config" jsonb NULL,
      "enabled" boolean NOT NULL DEFAULT true,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL,
      "created_by" character varying(36) NOT NULL,
      "updated_by" character varying(36) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    )""")
    op.execute('CREATE INDEX IF NOT EXISTS "idx_policy_workspace_id" ON "policy" ("workspace_id")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_policy_deleted_at" ON "policy" ("deleted_at")')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "policy" CASCADE')
