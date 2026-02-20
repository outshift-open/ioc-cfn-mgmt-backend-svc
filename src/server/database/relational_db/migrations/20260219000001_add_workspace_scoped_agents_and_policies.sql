-- Migration: Add workspace-scoped cognitive agents and policies
-- Version: 2026-02-19
-- Description:
--   - Convert cognitive_agent from global to workspace-scoped
--   - Add new policy table (workspace-scoped)

BEGIN;

-- ====================
-- Update: cognitive_agent (Convert to workspace-scoped)
-- ====================

-- Drop unique index on cognitive_agent_name (no longer globally unique)
DROP INDEX IF EXISTS "idx_ca_name_unique";

-- Add workspace_id column (nullable initially for existing data)
ALTER TABLE "cognitive_agent"
  ADD COLUMN IF NOT EXISTS "workspace_id" character varying(36);

-- Add audit columns
ALTER TABLE "cognitive_agent"
  ADD COLUMN IF NOT EXISTS "created_by" character varying(36);

ALTER TABLE "cognitive_agent"
  ADD COLUMN IF NOT EXISTS "updated_by" character varying(36);

ALTER TABLE "cognitive_agent"
  ADD COLUMN IF NOT EXISTS "deleted_at" timestamp NULL;

-- Create index on workspace_id
CREATE INDEX IF NOT EXISTS "idx_ca_workspace_id" ON "cognitive_agent" ("workspace_id");

-- Create index on deleted_at
CREATE INDEX IF NOT EXISTS "idx_ca_deleted_at" ON "cognitive_agent" ("deleted_at");

-- Note: workspace_id will be set to NOT NULL after data migration
-- For now, leave it nullable to allow existing data to remain

-- ====================
-- Table: policy (Workspace-scoped)
-- ====================
CREATE TABLE IF NOT EXISTS "policy" (
  "policy_id" character varying(255) NOT NULL,
  "workspace_id" character varying(36) NOT NULL,
  "policy_name" character varying(255) NOT NULL,
  "config" jsonb NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NULL,
  "created_by" character varying(36) NOT NULL,
  "updated_by" character varying(36) NULL,
  "deleted_at" timestamp NULL,
  PRIMARY KEY ("policy_id")
);

-- Create indexes for policy table
CREATE INDEX IF NOT EXISTS "idx_policy_workspace_id" ON "policy" ("workspace_id");
CREATE INDEX IF NOT EXISTS "idx_policy_deleted_at" ON "policy" ("deleted_at");

COMMIT;
