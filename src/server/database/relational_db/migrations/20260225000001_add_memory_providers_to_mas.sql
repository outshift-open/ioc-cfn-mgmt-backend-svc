-- Migration: Add memory providers to Multi-Agentic System
-- Description: Add shared_memory_provider_id to MAS table to support shared memory across agents
-- The agents JSONB field will store per-agent memory provider configuration
-- Date: 2026-02-25

-- Add shared_memory_provider_id column to multi_agentic_system table
ALTER TABLE multi_agentic_system
    ADD COLUMN shared_memory_provider_id VARCHAR(255);

-- Add foreign key constraint to memory_provider table
ALTER TABLE multi_agentic_system
    ADD CONSTRAINT fk_mas_shared_memory_provider
    FOREIGN KEY (shared_memory_provider_id)
    REFERENCES memory_provider(memory_provider_id)
    ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX idx_mas_shared_memory_provider_id ON multi_agentic_system(shared_memory_provider_id);

-- Add comment
COMMENT ON COLUMN multi_agentic_system.shared_memory_provider_id IS 'Shared memory provider ID for all agents in this MAS';
