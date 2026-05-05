-- Migration: Add config_timestamp to cognition_fabric_node
-- Version: 2026-02-23
-- Description:
--   - Add config_timestamp column to track when CFN config last changed
--   - Used for change detection: CFN compares its stored timestamp with mgmt service timestamp
--   - If timestamps differ, CFN fetches updated config via GET endpoint

-- ====================
-- Update: cognition_fabric_node (Add config_timestamp)
-- ====================

-- Add config_timestamp column (defaults to CURRENT_TIMESTAMP)
ALTER TABLE "cognition_fabric_node"
  ADD COLUMN IF NOT EXISTS "config_timestamp" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- Create index on config_timestamp for efficient queries
CREATE INDEX IF NOT EXISTS "idx_cfn_config_timestamp" ON "cognition_fabric_node" ("config_timestamp");

-- Update existing rows to set config_timestamp to updated_at (or created_at if updated_at is null)
UPDATE "cognition_fabric_node"
  SET "config_timestamp" = COALESCE("updated_at", "created_at")
  WHERE "config_timestamp" IS NULL OR "config_timestamp" = CURRENT_TIMESTAMP;
