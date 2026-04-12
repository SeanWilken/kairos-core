-- 0001_initial_onboarding.sql
-- Initial schema for bootstrap sessions, runtime checks, and ingest jobs.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS bootstrap_sessions (
  session_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  status TEXT NOT NULL,
  runtime_json JSONB NOT NULL,
  database_json JSONB NOT NULL,
  deployment_json JSONB NOT NULL,
  secrets_json JSONB NOT NULL,
  vector_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_check_runs (
  run_id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES bootstrap_sessions(session_id) ON DELETE CASCADE,
  checks_json JSONB NOT NULL,
  summary_json JSONB NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
  job_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES bootstrap_sessions(session_id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  source_files_json JSONB NOT NULL,
  chunking_profile TEXT NOT NULL,
  embedding_profile TEXT NOT NULL,
  result_json JSONB,
  error_json JSONB,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bootstrap_sessions_scope ON bootstrap_sessions (tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_runtime_check_runs_session ON runtime_check_runs (session_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_session ON ingest_jobs (session_id, created_at DESC);
