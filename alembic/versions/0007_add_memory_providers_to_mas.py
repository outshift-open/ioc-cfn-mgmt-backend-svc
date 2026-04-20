"""add memory providers to MAS

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-25 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE multi_agentic_system ADD COLUMN shared_memory_provider_id VARCHAR(255)")
    op.execute("""ALTER TABLE multi_agentic_system ADD CONSTRAINT fk_mas_shared_memory_provider FOREIGN KEY (shared_memory_provider_id) REFERENCES memory_provider(memory_provider_id) ON DELETE SET NULL""")
    op.execute("CREATE INDEX idx_mas_shared_memory_provider_id ON multi_agentic_system(shared_memory_provider_id)")
    op.execute("COMMENT ON COLUMN multi_agentic_system.shared_memory_provider_id IS 'Shared memory provider ID for all agents in this MAS'")


def downgrade() -> None:
    op.execute("ALTER TABLE multi_agentic_system DROP CONSTRAINT IF EXISTS fk_mas_shared_memory_provider")
    op.execute("ALTER TABLE multi_agentic_system DROP COLUMN IF EXISTS shared_memory_provider_id")
