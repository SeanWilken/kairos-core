-- 0019_prompt_templates.sql

CREATE TABLE IF NOT EXISTS prompt_template_versions (
  template_version_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  provider_id TEXT NOT NULL DEFAULT 'openai',
  template_kind TEXT NOT NULL DEFAULT 'system_prompt',
  name TEXT NOT NULL DEFAULT 'default',
  version INTEGER NOT NULL DEFAULT 1,
  content TEXT NOT NULL DEFAULT '',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_template_versions_scope
  ON prompt_template_versions(tenant_id, provider_id, template_kind, name);

CREATE TABLE IF NOT EXISTS prompt_template_activations (
  activation_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  scope_level TEXT NOT NULL DEFAULT 'tenant',
  scope_id TEXT NOT NULL DEFAULT '',
  provider_id TEXT NOT NULL DEFAULT 'openai',
  template_kind TEXT NOT NULL DEFAULT 'system_prompt',
  template_version_id TEXT NOT NULL REFERENCES prompt_template_versions(template_version_id) ON DELETE CASCADE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  reason TEXT NOT NULL DEFAULT '',
  rolled_back_from_activation_id TEXT NOT NULL DEFAULT '',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_template_activations_lookup
  ON prompt_template_activations(tenant_id, scope_level, scope_id, provider_id, template_kind, is_active);
