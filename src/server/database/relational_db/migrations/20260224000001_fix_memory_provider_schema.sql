-- Migration: Fix memory_provider schema
-- Date: 2026-02-24
-- Description: Remove provider_type and provider columns, add unique constraint on memory_provider_name
-- Related to commit: cd56b5f (Fix memory provider #44)

-- Remove the provider_type column 
ALTER TABLE "memory_provider" DROP COLUMN IF EXISTS "provider_type";

-- Remove the provider column 
ALTER TABLE "memory_provider" DROP COLUMN IF EXISTS "provider";

-- Add unique constraint on memory_provider_name (where not deleted)
CREATE UNIQUE INDEX IF NOT EXISTS "idx_mp_name_unique" 
ON "memory_provider" ("name")
WHERE "deleted_at" IS NULL;
