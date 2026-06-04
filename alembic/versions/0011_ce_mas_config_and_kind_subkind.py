"""CE mas_config per-MAS overrides, kind/subkind, and mas_auto_associate

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-03 00:00:00

Changes:
  - Drop task_schedule from multi_agentic_system (schedule belongs in CE mas_config)
  - Add mas_config (JSONB, nullable) to mas_cognition_engines junction table
    to store the effective per-MAS CE config (copied from CE mas_config on association,
    overridable per MAS via the management plane)
  - Drop type from cognition_engine
  - Add kind (String(50), nullable) to cognition_engine
  - Add subkind (String(50), nullable) to cognition_engine
  - Rename auto_attach -> mas_auto_associate on cognition_engine
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

    # Add mas_config to junction table for per-MAS CE config overrides
    op.add_column("mas_cognition_engines", sa.Column("mas_config", JSONB, nullable=True))

    # Replace CE type with kind + subkind
    op.drop_column("cognition_engine", "type")
    op.add_column("cognition_engine", sa.Column("kind", sa.String(50), nullable=True))
    op.add_column("cognition_engine", sa.Column("subkind", sa.String(50), nullable=True))

    # Rename auto_attach -> mas_auto_associate
    op.alter_column("cognition_engine", "auto_attach", new_column_name="mas_auto_associate")


def downgrade() -> None:
    op.alter_column("cognition_engine", "mas_auto_associate", new_column_name="auto_attach")
    op.drop_column("cognition_engine", "subkind")
    op.drop_column("cognition_engine", "kind")
    op.add_column("cognition_engine", sa.Column("type", sa.String(50), nullable=False, server_default="custom"))
    op.drop_column("mas_cognition_engines", "mas_config")
    op.add_column("multi_agentic_system", sa.Column("task_schedule", JSONB, nullable=True))
