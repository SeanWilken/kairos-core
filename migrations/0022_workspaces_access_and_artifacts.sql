-- 0022_workspaces_access_and_artifacts.sql

CREATE TABLE IF NOT EXISTS workspace_records (
  workspace_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'window',
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  schema_version TEXT NOT NULL DEFAULT 'v1',
  state_version INTEGER NOT NULL DEFAULT 1,
  revision INTEGER NOT NULL DEFAULT 1,
  thread_binding_json TEXT NOT NULL DEFAULT '{}',
  state_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  archived_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_records_tenant_org ON workspace_records(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_workspace_records_status ON workspace_records(status);

CREATE TABLE IF NOT EXISTS app_access_grants (
  grant_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  app_id TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  feature_flags_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active',
  granted_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_app_access_grants_org_user_app UNIQUE (org_id, user_id, app_id)
);

CREATE INDEX IF NOT EXISTS idx_app_access_grants_tenant_org ON app_access_grants(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_app_access_grants_user_app ON app_access_grants(user_id, app_id);

CREATE TABLE IF NOT EXISTS generated_artifacts (
  artifact_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  channel_id TEXT NULL REFERENCES studio_channels(channel_id) ON DELETE SET NULL,
  workspace_id TEXT NULL REFERENCES workspace_records(workspace_id) ON DELETE SET NULL,
  orchestration_run_id TEXT NOT NULL DEFAULT '',
  message_id TEXT NOT NULL DEFAULT '',
  artifact_type TEXT NOT NULL DEFAULT 'markdown',
  producer_type TEXT NOT NULL DEFAULT 'persona',
  producer_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_artifacts_tenant_org ON generated_artifacts(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_generated_artifacts_channel ON generated_artifacts(channel_id);
CREATE INDEX IF NOT EXISTS idx_generated_artifacts_workspace ON generated_artifacts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_generated_artifacts_type ON generated_artifacts(artifact_type);
