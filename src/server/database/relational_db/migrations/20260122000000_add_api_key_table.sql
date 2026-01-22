-- Create "api_key" table
CREATE TABLE "api_key" (
  "id" character varying(36) NOT NULL DEFAULT (gen_random_uuid())::text,
  "workspace_id" character varying(36) NULL,
  "key_hash" character varying(256) NOT NULL,
  "key_preview" character varying(20) NOT NULL,
  "name" character varying(200) NOT NULL,
  "roles" character varying[] NOT NULL,
  "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "deleted_at" timestamp NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "api_key_workspace_id_fkey" FOREIGN KEY ("workspace_id") REFERENCES "workspace" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_api_key_workspace_id" to table: "api_key"
CREATE INDEX "idx_api_key_workspace_id" ON "api_key" ("workspace_id");
-- Create index "idx_api_key_deleted_at" to table: "api_key"
CREATE INDEX "idx_api_key_deleted_at" ON "api_key" ("deleted_at");
-- Create index "idx_api_key_key_hash" to table: "api_key"
CREATE INDEX "idx_api_key_key_hash" ON "api_key" ("key_hash");
