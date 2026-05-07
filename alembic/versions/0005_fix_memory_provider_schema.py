"""fix memory_provider schema

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-24 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "memory_provider" DROP COLUMN IF EXISTS "provider_type"')
    op.execute('ALTER TABLE "memory_provider" DROP COLUMN IF EXISTS "provider"')
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS "idx_mp_name_unique" ON "memory_provider" ("name") WHERE "deleted_at" IS NULL""")


def downgrade() -> None:
    pass
