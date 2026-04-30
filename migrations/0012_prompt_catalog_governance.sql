-- 0012_prompt_catalog_governance.sql
-- Adds persona approval controls and prompt catalog bundle provenance.

ALTER TABLE studio_personas
  ADD COLUMN IF NOT EXISTS approval_status TEXT NOT NULL DEFAULT 'draft';

ALTER TABLE studio_personas
  ADD COLUMN IF NOT EXISTS approved_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL;

ALTER TABLE studio_personas
  ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS prompt_catalog_bundles (
  bundle_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  bundle_version TEXT NOT NULL,
  checksum_sha256 TEXT NOT NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  signature_alg TEXT NOT NULL DEFAULT '',
  signature_key_id TEXT NOT NULL DEFAULT '',
  signature_value TEXT NOT NULL DEFAULT '',
  imported_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_prompt_catalog_bundles_tenant_bundle UNIQUE (tenant_id, bundle_id)
);

CREATE INDEX IF NOT EXISTS idx_prompt_catalog_bundles_tenant ON prompt_catalog_bundles(tenant_id);
