-- Migration: Add config_version to cognition_fabric_node
-- Date: 2026-02-23
-- Description:
--   - Add config_version column to track config changes via monotonic integer counter

-- Update: cognition_fabric_node (Add config_version)
-- This replaces the previous config_timestamp approach with a simpler integer counter

-- Add config_version column (defaults to 0)
ALTER TABLE "cognition_fabric_node"
  ADD COLUMN IF NOT EXISTS "config_version" integer NOT NULL DEFAULT 0;
