# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""CE kinds_subkinds, subprotocols, and category

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-08 00:00:00

Changes:
  - Replace kind (String) with kinds_subkinds (JSONB dict mapping kind -> list of subkinds)
  - Remove subkind column (now nested under kinds_subkinds)
  - Add subprotocols (JSONB list)
  - Add category (String) - 'unknown', 'gat', or 'cog' (default)
  - Migrate existing kind/subkind data to new structure
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns (kinds_subkinds starts nullable for migration, then set NOT NULL)
    op.add_column("cognition_engine", sa.Column("kinds_subkinds", JSONB, nullable=True))
    op.add_column("cognition_engine", sa.Column("subprotocols", JSONB, nullable=True, server_default="[]"))
    op.add_column("cognition_engine", sa.Column("category", sa.String(20), nullable=False, server_default="COG"))

    # Migrate existing kind/subkind data to kinds_subkinds JSONB
    # If kind exists, create {kind: [subkind]} or {kind: []} if subkind is null
    op.execute(
        """
        UPDATE cognition_engine
        SET kinds_subkinds = CASE
            WHEN kind IS NOT NULL AND subkind IS NOT NULL THEN jsonb_build_object(kind, jsonb_build_array(subkind))
            WHEN kind IS NOT NULL THEN jsonb_build_object(kind, '[]'::jsonb)
            ELSE '{}'::jsonb
        END
        """
    )

    # Make kinds_subkinds NOT NULL after migration (required for L9 routing)
    op.alter_column("cognition_engine", "kinds_subkinds", existing_type=JSONB, nullable=False)

    # Drop old columns
    op.drop_column("cognition_engine", "kind")
    op.drop_column("cognition_engine", "subkind")


def downgrade() -> None:
    # Add back old columns
    op.add_column("cognition_engine", sa.Column("kind", sa.String(50), nullable=True))
    op.add_column("cognition_engine", sa.Column("subkind", sa.String(50), nullable=True))

    # Migrate kinds_subkinds back to kind/subkind (take first kind and first subkind)
    # Note: This is lossy - only the first kind/subkind pair is preserved
    op.execute(
        """
        WITH first_kind AS (
            SELECT id, (jsonb_each_text(kinds_subkinds)).key AS kind
            FROM cognition_engine
            WHERE kinds_subkinds IS NOT NULL AND kinds_subkinds != '{}'::jsonb
        )
        UPDATE cognition_engine ce
        SET kind = fk.kind,
            subkind = (kinds_subkinds->fk.kind->>0)
        FROM first_kind fk
        WHERE ce.id = fk.id
        """
    )

    # Drop new columns
    op.drop_column("cognition_engine", "kinds_subkinds")
    op.drop_column("cognition_engine", "subprotocols")
    op.drop_column("cognition_engine", "category")
