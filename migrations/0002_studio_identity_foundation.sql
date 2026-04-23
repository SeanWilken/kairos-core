-- 0002_studio_identity_foundation.sql
-- Initial Studio identity and organization tables.

CREATE TABLE IF NOT EXISTS studio_users (
  user_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  is_global_admin BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_users_tenant_email UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS studio_organizations (
  org_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'team',
  owner_user_id TEXT NULL REFERENCES studio_users(user_id),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_organizations_tenant_slug UNIQUE (tenant_id, slug)
);

CREATE TABLE IF NOT EXISTS studio_org_memberships (
  membership_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_org_memberships_org_user UNIQUE (org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_studio_users_tenant ON studio_users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_studio_organizations_tenant ON studio_organizations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_studio_org_memberships_org ON studio_org_memberships (org_id);
CREATE INDEX IF NOT EXISTS idx_studio_org_memberships_user ON studio_org_memberships (user_id);
