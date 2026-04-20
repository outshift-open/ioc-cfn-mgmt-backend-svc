"""add description to memory_provider

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-05 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""ALTER TABLE "memory_provider" ADD COLUMN IF NOT EXISTS "description" VARCHAR(1000) NULL""")


def downgrade() -> None:
    op.execute("""ALTER TABLE "memory_provider" DROP COLUMN IF EXISTS "description" """)
