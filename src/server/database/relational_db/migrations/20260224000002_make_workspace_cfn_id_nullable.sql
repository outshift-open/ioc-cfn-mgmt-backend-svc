-- Make cfn_id nullable in workspace table to support default workspace without CFN
-- Migration: 20260224000002_make_workspace_cfn_id_nullable.sql

-- Drop the foreign key constraint first
ALTER TABLE "workspace" DROP CONSTRAINT IF EXISTS "fk_workspace_cfn";

-- Make cfn_id nullable
ALTER TABLE "workspace" ALTER COLUMN "cfn_id" DROP NOT NULL;

-- Re-add the foreign key constraint
ALTER TABLE "workspace" ADD CONSTRAINT "fk_workspace_cfn"
  FOREIGN KEY ("cfn_id") REFERENCES "cognition_fabric_node" ("id") ON DELETE RESTRICT;
