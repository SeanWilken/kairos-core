CREATE TABLE IF NOT EXISTS daily_summaries (
  summary_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  summary_date TIMESTAMPTZ NOT NULL,
  highlights_json TEXT NOT NULL DEFAULT '[]',
  sections_json TEXT NOT NULL DEFAULT '{}',
  stats_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_daily_summaries_tenant_org_user_date UNIQUE (tenant_id, org_id, user_id, summary_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_summaries_tenant_org_user_date
  ON daily_summaries (tenant_id, org_id, user_id, summary_date DESC);
