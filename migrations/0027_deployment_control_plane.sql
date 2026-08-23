ALTER TABLE audit_events
  ADD COLUMN IF NOT EXISTS org_id TEXT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_studio_organizations_scope'
  ) THEN
    ALTER TABLE studio_organizations
      ADD CONSTRAINT uq_studio_organizations_scope UNIQUE (org_id, tenant_id);
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_org_created
  ON audit_events (tenant_id, org_id, created_at DESC);

CREATE TABLE IF NOT EXISTS deployment_registry_connections (
  registry_connection_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  registry_url TEXT NOT NULL,
  namespace TEXT NOT NULL DEFAULT '',
  credential_secret_ref TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  config_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_deployment_registry_name UNIQUE (tenant_id, org_id, name),
  CONSTRAINT uq_deployment_registry_scope UNIQUE (registry_connection_id, tenant_id, org_id),
  CONSTRAINT fk_deployment_registry_org_scope
    FOREIGN KEY (org_id, tenant_id) REFERENCES studio_organizations(org_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deployment_registry_org_status
  ON deployment_registry_connections (tenant_id, org_id, status);

CREATE TABLE IF NOT EXISTS deployment_environments (
  environment_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  environment_type TEXT NOT NULL DEFAULT 'development',
  status TEXT NOT NULL DEFAULT 'active',
  config_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_deployment_environment_slug UNIQUE (tenant_id, org_id, slug),
  CONSTRAINT uq_deployment_environment_scope UNIQUE (environment_id, tenant_id, org_id),
  CONSTRAINT fk_deployment_environment_org_scope
    FOREIGN KEY (org_id, tenant_id) REFERENCES studio_organizations(org_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deployment_environments_org_status
  ON deployment_environments (tenant_id, org_id, status);

CREATE TABLE IF NOT EXISTS deployment_releases (
  release_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  registry_connection_id TEXT NULL,
  component TEXT NOT NULL,
  version TEXT NOT NULL,
  artifact_type TEXT NOT NULL DEFAULT 'container',
  artifact_ref TEXT NOT NULL,
  artifact_digest TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'candidate',
  contract_version TEXT NOT NULL DEFAULT 'v1',
  migration_plan_json TEXT NOT NULL DEFAULT '{}',
  rollback_instructions TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'candidate',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_deployment_release_component_version UNIQUE (tenant_id, org_id, component, version),
  CONSTRAINT uq_deployment_release_scope UNIQUE (release_id, tenant_id, org_id),
  CONSTRAINT fk_deployment_release_registry_scope
    FOREIGN KEY (registry_connection_id, tenant_id, org_id)
    REFERENCES deployment_registry_connections(registry_connection_id, tenant_id, org_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_deployment_release_org_scope
    FOREIGN KEY (org_id, tenant_id) REFERENCES studio_organizations(org_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deployment_releases_org_component_channel
  ON deployment_releases (tenant_id, org_id, component, channel, created_at DESC);

CREATE TABLE IF NOT EXISTS deployment_declarations (
  deployment_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  release_id TEXT NOT NULL,
  component TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'declared',
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  supersedes_deployment_id TEXT NULL,
  desired_state_json TEXT NOT NULL DEFAULT '{}',
  notes TEXT NOT NULL DEFAULT '',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  superseded_at TIMESTAMPTZ NULL,
  CONSTRAINT uq_deployment_declaration_scope UNIQUE (deployment_id, tenant_id, org_id),
  CONSTRAINT fk_deployment_declaration_environment_scope
    FOREIGN KEY (environment_id, tenant_id, org_id)
    REFERENCES deployment_environments(environment_id, tenant_id, org_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_deployment_declaration_release_scope
    FOREIGN KEY (release_id, tenant_id, org_id)
    REFERENCES deployment_releases(release_id, tenant_id, org_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_deployment_declaration_supersedes_scope
    FOREIGN KEY (supersedes_deployment_id, tenant_id, org_id)
    REFERENCES deployment_declarations(deployment_id, tenant_id, org_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_deployment_declaration_org_scope
    FOREIGN KEY (org_id, tenant_id) REFERENCES studio_organizations(org_id, tenant_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_deployment_current_environment_component
  ON deployment_declarations (environment_id, component)
  WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_deployment_declarations_org_environment_created
  ON deployment_declarations (tenant_id, org_id, environment_id, created_at DESC);

CREATE TABLE IF NOT EXISTS deployment_runtime_check_runs (
  check_run_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  deployment_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unknown',
  checks_json TEXT NOT NULL DEFAULT '[]',
  summary_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'external',
  observed_at TIMESTAMPTZ NOT NULL,
  recorded_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_deployment_runtime_check_scope
    FOREIGN KEY (deployment_id, tenant_id, org_id)
    REFERENCES deployment_declarations(deployment_id, tenant_id, org_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_deployment_runtime_check_org_scope
    FOREIGN KEY (org_id, tenant_id) REFERENCES studio_organizations(org_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deployment_runtime_checks_deployment_observed
  ON deployment_runtime_check_runs (deployment_id, observed_at DESC);

COMMENT ON TABLE deployment_registry_connections IS 'Organization-scoped registry metadata containing secret references but never registry credentials.';
COMMENT ON TABLE deployment_releases IS 'Immutable release metadata resolved to an artifact digest and a reviewed migration plan.';
COMMENT ON TABLE deployment_declarations IS 'Desired deployment state only; records do not execute deployment operations.';
COMMENT ON TABLE deployment_runtime_check_runs IS 'Append-only observations reported by operators or future authenticated runners.';
