-- Migration: Add policy table
-- Version: 2026-02-19
-- Description:
--   - Add new policy table (workspace-scoped)

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
