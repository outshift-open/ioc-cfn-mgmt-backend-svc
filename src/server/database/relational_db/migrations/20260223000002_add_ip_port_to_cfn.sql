-- Add ip_address and port columns to cognitive_fabric_node table
-- Migration: 20260223000002_add_ip_port_to_cfn.sql

ALTER TABLE "cognitive_fabric_node"
ADD COLUMN "ip_address" VARCHAR(45) NULL,
ADD COLUMN "port" VARCHAR(5) NULL;

COMMENT ON COLUMN "cognitive_fabric_node"."ip_address" IS 'IP address of the CFN node (IPv4 or IPv6)';
COMMENT ON COLUMN "cognitive_fabric_node"."port" IS 'Port number of the CFN node (1-65535)';
