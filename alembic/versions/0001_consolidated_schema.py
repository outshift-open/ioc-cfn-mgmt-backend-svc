"""consolidated schema

Revision ID: 0001
Revises:
Create Date: 2026-01-28 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE "workspace" (
      "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
      "name" character varying(255) NOT NULL,
      "cfn_id" character varying(255) NOT NULL,
      "users" character varying[] NULL,
      "config" jsonb NULL,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      "created_by" character varying(255) NULL,
      "updated_by" character varying(255) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    );
    CREATE INDEX "idx_workspace_name" ON "workspace" ("name");
    CREATE INDEX "idx_workspace_deleted_at" ON "workspace" ("deleted_at");
    CREATE INDEX "idx_workspace_cfn_id" ON "workspace" ("cfn_id");

    CREATE TABLE "user" (
      "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
      "username" character varying(360) NOT NULL,
      "password" character varying(360) NOT NULL,
      "domain" character varying(360) NOT NULL,
      "role" character varying(200) NOT NULL,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    );
    CREATE INDEX "idx_user_deleted_at" ON "user" ("deleted_at");
    CREATE UNIQUE INDEX "idx_user_username_unique" ON "user" ("username") WHERE "deleted_at" IS NULL;

    CREATE TABLE "api_key" (
      "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
      "user_id" character varying(36) NOT NULL,
      "key_hash" character varying(256) NOT NULL,
      "key_preview" character varying(20) NOT NULL,
      "name" character varying(200) NOT NULL,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    );
    CREATE INDEX "idx_api_key_user_id" ON "api_key" ("user_id");
    CREATE INDEX "idx_api_key_deleted_at" ON "api_key" ("deleted_at");
    CREATE INDEX "idx_api_key_key_hash" ON "api_key" ("key_hash");
    CREATE UNIQUE INDEX "idx_api_key_user_name_unique" ON "api_key" ("user_id", "name") WHERE "deleted_at" IS NULL;


    CREATE TABLE "workspace_member" (
      "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
      "workspace_id" character varying(36) NOT NULL,
      "user_id" character varying(36) NOT NULL,
      "role" character varying(50) NOT NULL,
      "joined_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "created_by" character varying(255) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id"),
      CONSTRAINT "fk_workspace_member_workspace" FOREIGN KEY ("workspace_id") REFERENCES "workspace" ("id"),
      CONSTRAINT "fk_workspace_member_user" FOREIGN KEY ("user_id") REFERENCES "user" ("id")
    );
    CREATE UNIQUE INDEX "idx_workspace_member_unique" ON "workspace_member" ("workspace_id", "user_id") WHERE "deleted_at" IS NULL;
    CREATE INDEX "idx_workspace_member_workspace_id" ON "workspace_member" ("workspace_id");
    CREATE INDEX "idx_workspace_member_user_id" ON "workspace_member" ("user_id");
    CREATE INDEX "idx_workspace_member_deleted_at" ON "workspace_member" ("deleted_at");

    CREATE TABLE "workspace_invitation" (
      "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
      "workspace_id" character varying(36) NOT NULL,
      "inviter_id" character varying(36) NOT NULL,
      "invitee_username" character varying(360) NOT NULL,
      "role" character varying(50) NOT NULL,
      "status" character varying(50) NOT NULL DEFAULT 'pending',
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "expires_at" timestamp NOT NULL,
      "responded_at" timestamp NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id"),
      CONSTRAINT "fk_workspace_invitation_workspace" FOREIGN KEY ("workspace_id") REFERENCES "workspace" ("id"),
      CONSTRAINT "fk_workspace_invitation_inviter" FOREIGN KEY ("inviter_id") REFERENCES "user" ("id")
    );
    CREATE INDEX "idx_workspace_invitation_workspace_id" ON "workspace_invitation" ("workspace_id");
    CREATE INDEX "idx_workspace_invitation_invitee_username" ON "workspace_invitation" ("invitee_username");
    CREATE INDEX "idx_workspace_invitation_status" ON "workspace_invitation" ("status");
    CREATE INDEX "idx_workspace_invitation_expires_at" ON "workspace_invitation" ("expires_at");
    CREATE INDEX "idx_workspace_invitation_deleted_at" ON "workspace_invitation" ("deleted_at");

    CREATE TABLE "multi_agentic_system" (
      "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
      "workspace_id" character varying(36) NOT NULL,
      "name" character varying(255) NOT NULL,
      "description" text NULL,
      "agents" jsonb NULL,
      "config" jsonb NULL,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      "created_by" character varying(255) NULL,
      "updated_by" character varying(255) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id"),
      CONSTRAINT "fk_multi_agentic_system_workspace" FOREIGN KEY ("workspace_id") REFERENCES "workspace" ("id")
    );
    CREATE INDEX "idx_mas_workspace_id" ON "multi_agentic_system" ("workspace_id");
    CREATE INDEX "idx_mas_deleted_at" ON "multi_agentic_system" ("deleted_at");
    CREATE UNIQUE INDEX "idx_mas_workspace_name_unique" ON "multi_agentic_system" ("workspace_id", "name") WHERE "deleted_at" IS NULL;

    CREATE TABLE "cognition_fabric_node" (
      "id" character varying(255) NOT NULL,
      "name" character varying(255) NOT NULL,
      "cfn_config" jsonb NULL,
      "config" jsonb NULL,
      "status" character varying(50) NOT NULL DEFAULT 'online',
      "last_seen" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "enabled" boolean NOT NULL DEFAULT true,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      "created_by" character varying(255) NULL,
      "updated_by" character varying(255) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    );
    CREATE INDEX "idx_cfn_enabled" ON "cognition_fabric_node" ("enabled");
    CREATE INDEX "idx_cfn_deleted_at" ON "cognition_fabric_node" ("deleted_at");
    CREATE INDEX "idx_cfn_last_seen" ON "cognition_fabric_node" ("last_seen");
    CREATE INDEX "idx_cfn_status" ON "cognition_fabric_node" ("status");
    CREATE UNIQUE INDEX "idx_cfn_name_unique" ON "cognition_fabric_node" ("name") WHERE (deleted_at IS NULL);

    ALTER TABLE "workspace" ADD CONSTRAINT "fk_workspace_cfn"
      FOREIGN KEY ("cfn_id") REFERENCES "cognition_fabric_node" ("id") ON DELETE RESTRICT;

    CREATE TABLE "memory_provider" (
      "id" character varying(255) NOT NULL,
      "name" character varying(255) NOT NULL,
      "description" character varying(1000) NULL,
      "config" jsonb NULL,
      "enabled" boolean NOT NULL DEFAULT true,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL,
      "created_by" character varying(36) NOT NULL,
      "updated_by" character varying(36) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    );
    CREATE UNIQUE INDEX "idx_mp_name_unique" ON "memory_provider" ("name") WHERE "deleted_at" IS NULL;

CREATE TABLE "cognition_engine" (
      "id" character varying(255) NOT NULL,
      "workspace_id" character varying(36) NOT NULL,
      "name" character varying(255) NOT NULL,
      "config" jsonb NULL,
      "enabled" boolean NOT NULL DEFAULT true,
      "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      "updated_at" timestamp NULL,
      "created_by" character varying(36) NOT NULL,
      "updated_by" character varying(36) NULL,
      "deleted_at" timestamp NULL,
      PRIMARY KEY ("id")
    );
    CREATE INDEX "idx_ce_workspace_id" ON "cognition_engine" ("workspace_id");

    """)


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS "cognition_engine" CASCADE')
    op.execute('DROP TABLE IF EXISTS "memory_provider" CASCADE')
    op.execute('DROP TABLE IF EXISTS "cognition_fabric_node" CASCADE')
    op.execute('DROP TABLE IF EXISTS "multi_agentic_system" CASCADE')
    op.execute('DROP TABLE IF EXISTS "workspace_invitation" CASCADE')
    op.execute('DROP TABLE IF EXISTS "workspace_member" CASCADE')
    op.execute('DROP TABLE IF EXISTS "api_key" CASCADE')
    op.execute('DROP TABLE IF EXISTS "user" CASCADE')
    op.execute('DROP TABLE IF EXISTS "workspace" CASCADE')
