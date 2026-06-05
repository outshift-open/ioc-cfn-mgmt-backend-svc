"""Drop task_schedule from MAS

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-03 00:00:00

Changes:
  - Drop task_schedule from multi_agentic_system (schedule now lives in CE mas_config)

Note: All CE changes (kind/subkind, mas_auto_associate, mas_config) already in migration 0010
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop task_schedule from MAS (schedule now lives inside CE mas_config)
    op.drop_column("multi_agentic_system", "task_schedule")


def downgrade() -> None:
    op.add_column("multi_agentic_system", sa.Column("task_schedule", JSONB, nullable=True))
