"""add ip_address and port to cfn

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-23 00:00:02
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""ALTER TABLE "cognitive_fabric_node" ADD COLUMN "ip_address" VARCHAR(45) NULL, ADD COLUMN "port" VARCHAR(5) NULL""")
    op.execute("""COMMENT ON COLUMN "cognitive_fabric_node"."ip_address" IS 'IP address of the CFN node (IPv4 or IPv6)'""")
    op.execute("""COMMENT ON COLUMN "cognitive_fabric_node"."port" IS 'Port number of the CFN node (1-65535)'""")


def downgrade() -> None:
    op.execute("""ALTER TABLE "cognitive_fabric_node" DROP COLUMN IF EXISTS "port" """)
    op.execute("""ALTER TABLE "cognitive_fabric_node" DROP COLUMN IF EXISTS "ip_address" """)
