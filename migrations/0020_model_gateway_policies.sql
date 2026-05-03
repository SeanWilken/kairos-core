-- 0020_model_gateway_policies.sql

CREATE TABLE IF NOT EXISTS model_gateway_policies (
  policy_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  name TEXT NOT NULL DEFAULT 'default',
  version INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'draft',
  config_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  rolled_back_from_policy_id TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_model_gateway_policies_tenant_org
  ON model_gateway_policies(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_model_gateway_policies_status
  ON model_gateway_policies(status);
