-- Initial Database Schema
-- Consolidated migration containing all necessary tables

-- ====================
-- Table: workspace
-- ====================
CREATE TABLE "workspace" (
  "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
  "name" character varying(255) NOT NULL,
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
-- Table: audit
-- ====================
CREATE TABLE "audit" (
  "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
  "request_id" character varying(36) NULL,
  "resource_type" character varying(360) NOT NULL,
  "audit_type" character varying(360) NOT NULL,
  "audit_resource_id" character varying(360) NULL,
  "created_by" character varying(360) NULL,
  "updated_by" character varying(360) NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" timestamp NULL,
  "deleted_by" character varying(360) NULL,
  "audit_information" json NULL,
  "audit_extra_information" text NULL,
  PRIMARY KEY ("id")
);

CREATE INDEX "idx_audit_audit_resource_id" ON "audit" ("audit_resource_id");
CREATE INDEX "idx_audit_deleted_at" ON "audit" ("deleted_at");
CREATE INDEX "idx_audit_request_id" ON "audit" ("request_id");

-- ====================
-- Table: workspace_member
-- ====================
-- Tracks actual workspace membership with roles
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

-- Unique constraint: one user can only be a member once per workspace
CREATE UNIQUE INDEX "idx_workspace_member_unique" ON "workspace_member" ("workspace_id", "user_id") WHERE "deleted_at" IS NULL;
CREATE INDEX "idx_workspace_member_workspace_id" ON "workspace_member" ("workspace_id");
CREATE INDEX "idx_workspace_member_user_id" ON "workspace_member" ("user_id");
CREATE INDEX "idx_workspace_member_deleted_at" ON "workspace_member" ("deleted_at");

-- ====================
-- Table: workspace_invitation
-- ====================
-- Tracks pending invitations with expiration
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
