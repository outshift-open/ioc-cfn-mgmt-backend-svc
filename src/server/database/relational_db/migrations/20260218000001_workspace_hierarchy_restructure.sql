-- Workspace Hierarchy Restructure Migration
-- 1. Create memory_provider table (shared across workspaces) + workspace_memory_provider join table
-- 2. Create cognitive_engine table
-- 3. Remove workspace_id FK from cognitive_fabric_node; add cfn_workspace join table
-- 4. Create cognitive_agent table (global, read-only built-in defaults)

-- ====================
-- 1a. Create memory_provider table (shared resource, no workspace_id)
-- ====================
CREATE TABLE "memory_provider" (
  "memory_provider_id" character varying(255) NOT NULL,
  "memory_provider_name" character varying(255) NOT NULL,
  "provider_type" character varying(50) NOT NULL,
  "provider" character varying(100) NOT NULL,
  "config" jsonb NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NULL,
  "created_by" character varying(36) NOT NULL,
  "updated_by" character varying(36) NULL,
  "deleted_at" timestamp NULL,
  PRIMARY KEY ("memory_provider_id")
);

-- ====================
-- 1b. Create workspace_memory_provider join table (many-to-many)
-- ====================
CREATE TABLE "workspace_memory_provider" (
  "workspace_id" character varying(36) NOT NULL,
  "memory_provider_id" character varying(255) NOT NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_by" character varying(255) NULL,
  PRIMARY KEY ("workspace_id", "memory_provider_id"),
  CONSTRAINT "fk_wmp_workspace" FOREIGN KEY ("workspace_id") REFERENCES "workspace" ("id") ON DELETE CASCADE,
  CONSTRAINT "fk_wmp_memory_provider" FOREIGN KEY ("memory_provider_id") REFERENCES "memory_provider" ("memory_provider_id") ON DELETE CASCADE
);

CREATE INDEX "idx_wmp_workspace_id" ON "workspace_memory_provider" ("workspace_id");
CREATE INDEX "idx_wmp_memory_provider_id" ON "workspace_memory_provider" ("memory_provider_id");

-- ====================
-- 2. Create cognitive_engine table (workspace-scoped)
-- ====================
CREATE TABLE "cognitive_engine" (
  "cognitive_engine_id" character varying(255) NOT NULL,
  "workspace_id" character varying(36) NOT NULL,
  "cognitive_engine_name" character varying(255) NOT NULL,
  "config" jsonb NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NULL,
  "created_by" character varying(36) NOT NULL,
  "updated_by" character varying(36) NULL,
  "deleted_at" timestamp NULL,
  PRIMARY KEY ("cognitive_engine_id")
);

CREATE INDEX "idx_ce_workspace_id" ON "cognitive_engine" ("workspace_id");

-- ====================
-- 3a. cognitive_fabric_node: remove workspace_id, update unique constraint
-- ====================
DROP INDEX IF EXISTS "idx_cfn_workspace_id";
DROP INDEX IF EXISTS "idx_cfn_workspace_name_unique";

ALTER TABLE "cognitive_fabric_node" DROP CONSTRAINT IF EXISTS "cognitive_fabric_node_workspace_id_fkey";
ALTER TABLE "cognitive_fabric_node" DROP COLUMN IF EXISTS "workspace_id";

CREATE UNIQUE INDEX "idx_cfn_name_unique" ON "cognitive_fabric_node" ("cfn_name") WHERE (deleted_at IS NULL);

-- ====================
-- 3b. Add cfn_id to workspace table (workspace chooses its CFN)
-- ====================
-- First, delete any existing workspaces (dev environment cleanup)
DELETE FROM "workspace_member" WHERE workspace_id IN (SELECT id FROM workspace);
DELETE FROM "workspace_invitation" WHERE workspace_id IN (SELECT id FROM workspace);
DELETE FROM "multi_agentic_system" WHERE workspace_id IN (SELECT id FROM workspace);
DELETE FROM "workspace";

-- Now add the cfn_id column as NOT NULL (all workspaces require a CFN)
ALTER TABLE "workspace" ADD COLUMN "cfn_id" character varying(255) NOT NULL;
ALTER TABLE "workspace" ADD CONSTRAINT "fk_workspace_cfn" 
  FOREIGN KEY ("cfn_id") REFERENCES "cognitive_fabric_node" ("cfn_id") ON DELETE RESTRICT;

CREATE INDEX "idx_workspace_cfn_id" ON "workspace" ("cfn_id");

-- Note: ON DELETE RESTRICT prevents deleting a CFN that has workspaces assigned to it
-- Workspaces must be reassigned to a different CFN before the original CFN can be deleted

-- ====================
-- 4. Create cognitive_agent table (global built-in defaults, read-only)
-- ====================
CREATE TABLE "cognitive_agent" (
  "cognitive_agent_id" character varying(255) NOT NULL,
  "cognitive_agent_name" character varying(255) NOT NULL,
  "description" character varying(1000) NULL,
  "config" jsonb NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NULL,
  PRIMARY KEY ("cognitive_agent_id")
);

CREATE UNIQUE INDEX "idx_ca_name_unique" ON "cognitive_agent" ("cognitive_agent_name");
