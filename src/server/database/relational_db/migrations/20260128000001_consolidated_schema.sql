-- Consolidated Database Schema
-- Version: 2026-02-19
-- Description: Complete database schema with all migrations consolidated
-- Includes:
--   - Base schema (workspace, user, audit, multi_agentic_system, api_key)
--   - Workspace hierarchy restructure (memory_provider, cognition_engine)
--   - CFN restructure (cfn_id on workspace, cfn_workspace join removed)
--   - Config naming update (cloud_config -> config)

-- ====================
-- Table: workspace
-- ====================
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

-- ====================
-- Table: user
-- ====================
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

-- ====================
-- Table: api_key (user-scoped)
-- ====================
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


-- ====================
-- Table: workspace_member
-- ====================
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

-- ====================
-- Table: workspace_invitation
-- ====================
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

-- ====================
-- Table: multi_agentic_system
-- ====================
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

-- ====================
-- Table: agent (Dedicated table for MAS agents)
-- ====================
CREATE TABLE "agent" (
  "agent_id" character varying(255) NOT NULL,
  "mas_id" character varying(36) NOT NULL,
  "name" character varying(255) NULL,
  "url" text NULL,
  "identity_type" character varying(50) NULL,
  "identity_identifiers" jsonb NULL,
  "agentic_memory_provider_id" character varying(255) NULL,
  "config" jsonb NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  "created_by" character varying(255) NULL,
  "updated_by" character varying(255) NULL,
  PRIMARY KEY ("agent_id"),
  CONSTRAINT "fk_agent_mas" FOREIGN KEY ("mas_id") REFERENCES "multi_agentic_system" ("id") ON DELETE CASCADE
);

CREATE INDEX "idx_agent_mas_id" ON "agent" ("mas_id");
CREATE INDEX "idx_agent_identity_type" ON "agent" ("identity_type");
CREATE INDEX "idx_agent_agentic_memory" ON "agent" ("agentic_memory_provider_id");
CREATE UNIQUE INDEX "uq_agent_mas_name" ON "agent" ("mas_id", "name") WHERE "name" IS NOT NULL;

-- ====================
-- Table: cognition_fabric_node (Global, no workspace FK)
-- ====================
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

-- Add FK from workspace to cognition_fabric_node (workspace chooses its CFN)
ALTER TABLE "workspace" ADD CONSTRAINT "fk_workspace_cfn"
  FOREIGN KEY ("cfn_id") REFERENCES "cognition_fabric_node" ("id") ON DELETE RESTRICT;

-- ====================
-- Table: memory_provider (Global, shared across workspaces)
-- ====================
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

-- Add FK from agent to memory_provider (created after memory_provider table exists)
ALTER TABLE "agent" ADD CONSTRAINT "fk_agent_memory_provider"
  FOREIGN KEY ("agentic_memory_provider_id") REFERENCES "memory_provider" ("id") ON DELETE SET NULL;

-- ====================
-- Table: cognition_engine (CFN-scoped)
-- ====================
CREATE TABLE "cognition_engine" (
  "id" character varying(255) NOT NULL DEFAULT (gen_random_uuid())::text,
  "cfn_id" character varying(255) NOT NULL,
  "name" character varying(255) NOT NULL,

  -- Connection info
  "url" character varying(512) NOT NULL,

  -- Authentication (optional - credentials for CFN to reach CE, encrypted)
  "auth" jsonb NULL,                       -- e.g. {"type": "api_key", "credentials": {"api_key": "..."}}
                                           -- type values: 'api_key', 'basic', 'bearer'

  -- Type and capabilities
  "type" character varying(50) NOT NULL DEFAULT 'custom', -- values: 'knowledge_management', 'semantic_negotiation', 'distillation', 'custom'
  "capabilities" jsonb NOT NULL DEFAULT '[]'::jsonb,
  "metrics" jsonb NOT NULL DEFAULT '[]'::jsonb,

  -- Versioning
  "version" character varying(50) NOT NULL,

  -- Status (managed by system)
  "status" character varying(20) NOT NULL DEFAULT 'offline', -- values: 'online', 'offline'
  "last_seen" timestamptz NULL,

  -- Lifecycle
  "enabled" boolean NOT NULL DEFAULT true,    -- toggled via PATCH; server-set true on creation
  "auto_attach" boolean NOT NULL DEFAULT false, -- if true, auto-associated with all MAS under the same CFN

  -- Configuration
  "config" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "mas_config" jsonb NOT NULL DEFAULT '{}'::jsonb,

  -- Audit fields
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "updated_at" timestamptz NULL,
  "deleted_at" timestamptz NULL,
  "created_by" character varying(36) NULL,
  "updated_by" character varying(36) NULL,

  PRIMARY KEY ("id"),
  CONSTRAINT "fk_ce_cfn" FOREIGN KEY ("cfn_id") REFERENCES "cognition_fabric_node" ("id")
);

CREATE INDEX "idx_ce_cfn_id" ON "cognition_engine" ("cfn_id");
CREATE INDEX "idx_ce_status" ON "cognition_engine" ("status");
CREATE INDEX "idx_ce_enabled" ON "cognition_engine" ("enabled");
CREATE INDEX "idx_ce_auto_attach" ON "cognition_engine" ("auto_attach");
CREATE UNIQUE INDEX "uq_ce_cfn_name_version" ON "cognition_engine" ("cfn_id", "name", "version") WHERE "deleted_at" IS NULL;

-- ====================
-- Table: mas_cognition_engines (MAS <-> CE junction)
-- ====================
CREATE TABLE "mas_cognition_engines" (
  "mas_id" character varying(36) NOT NULL,
  "ce_id" character varying(255) NOT NULL,
  "created_at" timestamptz NOT NULL DEFAULT NOW(),
  "created_by" character varying(255) NULL,

  CONSTRAINT "pk_mas_cognition_engines" PRIMARY KEY ("mas_id", "ce_id"),
  CONSTRAINT "fk_mas_ce_mas" FOREIGN KEY ("mas_id") REFERENCES "multi_agentic_system" ("id") ON DELETE CASCADE,
  CONSTRAINT "fk_mas_ce_ce" FOREIGN KEY ("ce_id") REFERENCES "cognition_engine" ("id") ON DELETE CASCADE
);

CREATE INDEX "idx_mas_ce_ce_id" ON "mas_cognition_engines" ("ce_id");

