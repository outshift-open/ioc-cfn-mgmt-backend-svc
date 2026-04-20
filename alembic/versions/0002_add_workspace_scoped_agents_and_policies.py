"""add workspace scoped agents and policies

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
    op.execute('DROP INDEX IF EXISTS "idx_ca_name_unique"')
    op.execute("""ALTER TABLE "cognitive_agent" ADD COLUMN IF NOT EXISTS "workspace_id" character varying(36)""")
    op.execute("""ALTER TABLE "cognitive_agent" ADD COLUMN IF NOT EXISTS "created_by" character varying(36)""")
    op.execute("""ALTER TABLE "cognitive_agent" ADD COLUMN IF NOT EXISTS "updated_by" character varying(36)""")
    op.execute("""ALTER TABLE "cognitive_agent" ADD COLUMN IF NOT EXISTS "deleted_at" timestamp NULL""")
    op.execute('CREATE INDEX IF NOT EXISTS "idx_ca_workspace_id" ON "cognitive_agent" ("workspace_id")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_ca_deleted_at" ON "cognitive_agent" ("deleted_at")')
    op.execute("""
    CREATE TABLE IF NOT EXISTS "policy" (
      "policy_id" character varying(255) NOT NULL,
      "workspace_id" character varying(36) NOT NULL,
      "policy_name" character varying(255) NOT NULL,
      "config" jsonb NULL,
      "enabled" boolean NOT NULL DEFAULT true,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL,
      "created_by" character varying(36) NOT NULL,
      "updated_by" character varying(36) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("policy_id")
    )""")
    op.execute('CREATE INDEX IF NOT EXISTS "idx_policy_workspace_id" ON "policy" ("workspace_id")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_policy_deleted_at" ON "policy" ("deleted_at")')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "policy" CASCADE')
    op.execute('DROP INDEX IF EXISTS "idx_ca_deleted_at"')
    op.execute('DROP INDEX IF EXISTS "idx_ca_workspace_id"')
    op.execute("""ALTER TABLE "cognitive_agent" DROP COLUMN IF EXISTS "deleted_at" """)
    op.execute("""ALTER TABLE "cognitive_agent" DROP COLUMN IF EXISTS "updated_by" """)
    op.execute("""ALTER TABLE "cognitive_agent" DROP COLUMN IF EXISTS "created_by" """)
    op.execute("""ALTER TABLE "cognitive_agent" DROP COLUMN IF EXISTS "workspace_id" """)
    op.execute('CREATE UNIQUE INDEX "idx_ca_name_unique" ON "cognitive_agent" ("cognitive_agent_name")')
