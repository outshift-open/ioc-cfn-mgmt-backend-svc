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
    # Add new columns
    op.add_column("cognition_engine", sa.Column("kinds_subkinds", JSONB, nullable=True, server_default="{}"))
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
        WHERE kind IS NOT NULL OR subkind IS NOT NULL
        """
    )

    # Drop old columns
    op.drop_column("cognition_engine", "kind")
    op.drop_column("cognition_engine", "subkind")


def downgrade() -> None:
    # Add back old columns
    op.add_column("cognition_engine", sa.Column("kind", sa.String(50), nullable=True))
    op.add_column("cognition_engine", sa.Column("subkind", sa.String(50), nullable=True))

    # Migrate kinds_subkinds back to kind/subkind (take first kind and first subkind)
    op.execute(
        """
        UPDATE cognition_engine
        SET kind = (SELECT jsonb_object_keys(kinds_subkinds) LIMIT 1),
            subkind = (
                SELECT value::text
                FROM jsonb_each(kinds_subkinds), jsonb_array_elements_text(value) AS value
                LIMIT 1
            )
        WHERE kinds_subkinds IS NOT NULL AND kinds_subkinds != '{}'::jsonb
        """
    )

    # Drop new columns
    op.drop_column("cognition_engine", "kinds_subkinds")
    op.drop_column("cognition_engine", "subprotocols")
    op.drop_column("cognition_engine", "category")
