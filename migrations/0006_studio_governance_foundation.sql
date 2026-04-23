-- 0006_studio_governance_foundation.sql
-- Adds governance bootstrap tables for invites, onboarding status, and org settings.

CREATE TABLE IF NOT EXISTS studio_org_invites (
  invite_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'pending',
  invited_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  accepted_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  expires_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_studio_org_invites_org ON studio_org_invites(org_id);
CREATE INDEX IF NOT EXISTS idx_studio_org_invites_tenant ON studio_org_invites(tenant_id);

CREATE TABLE IF NOT EXISTS studio_org_settings (
  setting_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  settings_json TEXT NOT NULL DEFAULT '{}',
  updated_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_org_settings_org UNIQUE (org_id)
);

CREATE INDEX IF NOT EXISTS idx_studio_org_settings_tenant ON studio_org_settings(tenant_id);

CREATE TABLE IF NOT EXISTS studio_org_onboarding (
  org_id TEXT PRIMARY KEY REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  tenant_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  checklist_json TEXT NOT NULL DEFAULT '{}',
  completed_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  completed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_studio_org_onboarding_tenant ON studio_org_onboarding(tenant_id);
