"""add config_version to cfn

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
    op.execute("""ALTER TABLE "cognition_fabric_node" ADD COLUMN IF NOT EXISTS "config_version" integer NOT NULL DEFAULT 0""")


def downgrade() -> None:
    op.execute("""ALTER TABLE "cognition_fabric_node" DROP COLUMN IF EXISTS "config_version" """)
