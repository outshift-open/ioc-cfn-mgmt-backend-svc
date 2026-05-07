"""make workspace cfn_id nullable

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-24 00:00:02
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "workspace" DROP CONSTRAINT IF EXISTS "fk_workspace_cfn"')
    op.execute('ALTER TABLE "workspace" ALTER COLUMN "cfn_id" DROP NOT NULL')
    op.execute("""ALTER TABLE "workspace" ADD CONSTRAINT "fk_workspace_cfn" FOREIGN KEY ("cfn_id") REFERENCES "cognition_fabric_node" ("id") ON DELETE RESTRICT""")


def downgrade() -> None:
    op.execute('ALTER TABLE "workspace" DROP CONSTRAINT IF EXISTS "fk_workspace_cfn"')
    op.execute('ALTER TABLE "workspace" ALTER COLUMN "cfn_id" SET NOT NULL')
    op.execute("""ALTER TABLE "workspace" ADD CONSTRAINT "fk_workspace_cfn" FOREIGN KEY ("cfn_id") REFERENCES "cognition_fabric_node" ("id") ON DELETE RESTRICT""")
