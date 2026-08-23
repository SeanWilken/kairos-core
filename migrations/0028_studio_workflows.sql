CREATE TABLE IF NOT EXISTS studio_workflow_definitions (
  workflow_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  spec_version TEXT NOT NULL DEFAULT 'v0.3',
  trigger_json TEXT NOT NULL DEFAULT '{}',
  nodes_json TEXT NOT NULL DEFAULT '[]',
  edges_json TEXT NOT NULL DEFAULT '[]',
  logic_rules_json TEXT NOT NULL DEFAULT '[]',
  policy_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_studio_workflow_definitions_org_name UNIQUE (tenant_id, org_id, name),
  CONSTRAINT uq_studio_workflow_definitions_scope UNIQUE (workflow_id, tenant_id, org_id),
  CONSTRAINT fk_studio_workflow_definition_org_scope
    FOREIGN KEY (org_id, tenant_id) REFERENCES studio_organizations(org_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_studio_workflow_definitions_tenant
  ON studio_workflow_definitions (tenant_id);

CREATE INDEX IF NOT EXISTS idx_studio_workflow_definitions_org
  ON studio_workflow_definitions (org_id);

CREATE TABLE IF NOT EXISTS workflow_runs (
  run_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  artifact_json TEXT NOT NULL DEFAULT '{}',
  review_context_json TEXT NOT NULL DEFAULT '{}',
  matched_rules_json TEXT NOT NULL DEFAULT '[]',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_workflow_runs_scope UNIQUE (run_id, tenant_id, org_id),
  CONSTRAINT fk_workflow_runs_definition_scope
    FOREIGN KEY (workflow_id, tenant_id, org_id)
    REFERENCES studio_workflow_definitions(workflow_id, tenant_id, org_id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow
  ON workflow_runs (workflow_id);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_tenant
  ON workflow_runs (tenant_id);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_org
  ON workflow_runs (org_id);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
  ON workflow_runs (status);

CREATE TABLE IF NOT EXISTS workflow_review_queue (
  review_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  node_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  reason_code TEXT NOT NULL DEFAULT '',
  requested_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  resolved_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  context_json TEXT NOT NULL DEFAULT '{}',
  requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ NULL,
  CONSTRAINT fk_workflow_review_definition_scope
    FOREIGN KEY (workflow_id, tenant_id, org_id)
    REFERENCES studio_workflow_definitions(workflow_id, tenant_id, org_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_workflow_review_run_scope
    FOREIGN KEY (run_id, tenant_id, org_id)
    REFERENCES workflow_runs(run_id, tenant_id, org_id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_review_queue_workflow
  ON workflow_review_queue (workflow_id);

CREATE INDEX IF NOT EXISTS idx_workflow_review_queue_tenant
  ON workflow_review_queue (tenant_id);

CREATE INDEX IF NOT EXISTS idx_workflow_review_queue_org
  ON workflow_review_queue (org_id);

CREATE INDEX IF NOT EXISTS idx_workflow_review_queue_run
  ON workflow_review_queue (run_id);

CREATE INDEX IF NOT EXISTS idx_workflow_review_queue_status
  ON workflow_review_queue (status);

COMMENT ON TABLE studio_workflow_definitions IS 'Organization-scoped Studio workflow specifications.';
COMMENT ON TABLE workflow_runs IS 'Durable execution state for Studio workflow runs.';
COMMENT ON TABLE workflow_review_queue IS 'Human-review work items raised by Studio workflow runs.';
