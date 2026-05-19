"""add unique constraint on agent (mas_id, name)

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-18 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS "uq_agent_mas_name" ON "agent" ("mas_id", "name") WHERE "name" IS NOT NULL""")


def downgrade() -> None:
    op.execute("""DROP INDEX IF EXISTS "uq_agent_mas_name" """)
