"""add config_timestamp to cfn

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-23 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""ALTER TABLE "cognitive_fabric_node" ADD COLUMN IF NOT EXISTS "config_timestamp" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP""")
    op.execute('CREATE INDEX IF NOT EXISTS "idx_cfn_config_timestamp" ON "cognitive_fabric_node" ("config_timestamp")')
    op.execute("""UPDATE "cognitive_fabric_node" SET "config_timestamp" = COALESCE("updated_at", "created_at") WHERE "config_timestamp" IS NULL OR "config_timestamp" = CURRENT_TIMESTAMP""")


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS "idx_cfn_config_timestamp"')
    op.execute("""ALTER TABLE "cognitive_fabric_node" DROP COLUMN IF EXISTS "config_timestamp" """)
