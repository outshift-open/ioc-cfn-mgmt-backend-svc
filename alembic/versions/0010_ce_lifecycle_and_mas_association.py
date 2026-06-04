"""CE lifecycle and MAS association

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-27 00:00:00

Changes:
  - Redesign cognition_engine as CFN-scoped resource:
    - Drop: workspace_id, old enabled column
    - Add: cfn_id (FK -> cognition_fabric_node), url, version, kind, subkind,
            auth, capabilities, metrics, config, mas_config, last_seen,
            enabled, mas_auto_associate, status
    - Update: config default -> '{}', created_by nullable, timestamps -> TIMESTAMPTZ
  - Unique key: (cfn_id, name, version) WHERE deleted_at IS NULL
    Same CE + same version upserts on re-registration; new version creates a new record
  - Add mas_cognition_engines junction table for MAS <-> CE many-to-many
    with mas_config (JSONB) for per-MAS config overrides
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- cognition_engine: drop old workspace-scoped columns ---
    op.drop_index("idx_ce_workspace_id", table_name="cognition_engine")
    op.drop_column("cognition_engine", "workspace_id")
    op.drop_column("cognition_engine", "enabled")

    # --- cognition_engine: add cfn_id FK ---
    op.add_column(
        "cognition_engine",
        sa.Column("cfn_id", sa.String(255), nullable=False, server_default=""),
    )
    op.alter_column("cognition_engine", "cfn_id", server_default=None)
    op.create_foreign_key(
        "fk_ce_cfn",
        "cognition_engine",
        "cognition_fabric_node",
        ["cfn_id"],
        ["id"],
    )
    op.create_index("idx_ce_cfn_id", "cognition_engine", ["cfn_id"])

    # --- cognition_engine: add required columns ---
    op.add_column(
        "cognition_engine",
        sa.Column("url", sa.String(512), nullable=False, server_default=""),
    )
    op.alter_column("cognition_engine", "url", server_default=None)

    op.add_column(
        "cognition_engine",
        sa.Column("version", sa.String(50), nullable=False, server_default=""),
    )
    op.alter_column("cognition_engine", "version", server_default=None)

    op.add_column(
        "cognition_engine",
        sa.Column("status", sa.String(20), nullable=False, server_default="offline"),
    )

    # --- cognition_engine: classification (optional) ---
    op.add_column("cognition_engine", sa.Column("kind", sa.String(50), nullable=True))
    op.add_column("cognition_engine", sa.Column("subkind", sa.String(50), nullable=True))

    # --- cognition_engine: add optional JSONB columns ---
    op.add_column("cognition_engine", sa.Column("auth", JSONB, nullable=True))
    op.add_column(
        "cognition_engine",
        sa.Column("capabilities", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "cognition_engine",
        sa.Column("metrics", JSONB, nullable=True, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "cognition_engine",
        sa.Column("mas_config", JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
    )

    # --- cognition_engine: add timestamp + update config default ---
    op.add_column(
        "cognition_engine",
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.alter_column(
        "cognition_engine",
        "config",
        server_default=sa.text("'{}'::jsonb"),
    )
    op.alter_column("cognition_engine", "created_by", nullable=True)

    # --- cognition_engine: migrate timestamps to TIMESTAMPTZ ---
    op.execute(
        "ALTER TABLE cognition_engine ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE cognition_engine ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE cognition_engine ALTER COLUMN deleted_at TYPE TIMESTAMPTZ USING deleted_at AT TIME ZONE 'UTC'"
    )

    # --- cognition_engine: unique key (cfn_id, name, version) WHERE not deleted ---
    op.create_index(
        "uq_ce_cfn_name_version",
        "cognition_engine",
        ["cfn_id", "name", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_ce_status", "cognition_engine", ["status"])

    # --- cognition_engine: add enabled and mas_auto_associate ---
    op.add_column(
        "cognition_engine",
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "cognition_engine",
        sa.Column("mas_auto_associate", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index("idx_ce_enabled", "cognition_engine", ["enabled"])
    op.create_index("idx_ce_mas_auto_associate", "cognition_engine", ["mas_auto_associate"])

    # --- mas_cognition_engines: junction table for MAS <-> CE many-to-many ---
    op.create_table(
        "mas_cognition_engines",
        sa.Column(
            "mas_id",
            sa.String(36),
            sa.ForeignKey("multi_agentic_system.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ce_id",
            sa.String(255),
            sa.ForeignKey("cognition_engine.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mas_config", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("mas_id", "ce_id", name="pk_mas_cognition_engines"),
    )
    op.create_index("idx_mas_ce_ce_id", "mas_cognition_engines", ["ce_id"])


def downgrade() -> None:
    # --- mas_cognition_engines ---
    op.drop_index("idx_mas_ce_ce_id", table_name="mas_cognition_engines")
    op.drop_table("mas_cognition_engines")

    # --- cognition_engine: enabled / mas_auto_associate ---
    op.drop_index("idx_ce_mas_auto_associate", table_name="cognition_engine")
    op.drop_index("idx_ce_enabled", table_name="cognition_engine")
    op.drop_column("cognition_engine", "mas_auto_associate")
    op.drop_column("cognition_engine", "enabled")

    # --- cognition_engine: indexes and unique key ---
    op.drop_index("idx_ce_status", table_name="cognition_engine")
    op.drop_index("uq_ce_cfn_name_version", table_name="cognition_engine")
    op.drop_index("idx_ce_cfn_id", table_name="cognition_engine")
    op.drop_constraint("fk_ce_cfn", "cognition_engine", type_="foreignkey")

    # --- cognition_engine: new columns ---
    op.drop_column("cognition_engine", "mas_config")
    op.drop_column("cognition_engine", "metrics")
    op.drop_column("cognition_engine", "capabilities")
    op.drop_column("cognition_engine", "auth")
    op.drop_column("cognition_engine", "last_seen")
    op.drop_column("cognition_engine", "status")
    op.drop_column("cognition_engine", "subkind")
    op.drop_column("cognition_engine", "kind")
    op.drop_column("cognition_engine", "version")
    op.drop_column("cognition_engine", "url")
    op.drop_column("cognition_engine", "cfn_id")

    # --- cognition_engine: restore workspace-scoped columns ---
    op.add_column(
        "cognition_engine",
        sa.Column("workspace_id", sa.String(36), nullable=False, server_default=""),
    )
    op.add_column(
        "cognition_engine",
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("idx_ce_workspace_id", "cognition_engine", ["workspace_id"])

    # --- cognition_engine: restore timestamps ---
    op.execute(
        "ALTER TABLE cognition_engine ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE cognition_engine ALTER COLUMN updated_at TYPE TIMESTAMP USING updated_at AT TIME ZONE 'UTC'"
    )
    op.execute(
        "ALTER TABLE cognition_engine ALTER COLUMN deleted_at TYPE TIMESTAMP USING deleted_at AT TIME ZONE 'UTC'"
    )

    op.alter_column("cognition_engine", "created_by", nullable=False)
    op.alter_column("cognition_engine", "config", server_default=None)
