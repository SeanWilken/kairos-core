-- 0017_fallback_approval_requests.sql
-- Approval queue for provider/model fallback execution.

CREATE TABLE IF NOT EXISTS fallback_approval_requests (
  request_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  room_id TEXT NOT NULL DEFAULT '',
  orchestration_run_id TEXT NOT NULL DEFAULT '',
  persona_id TEXT NOT NULL DEFAULT '',
  source_provider_id TEXT NOT NULL DEFAULT '',
  source_model_id TEXT NOT NULL DEFAULT '',
  fallback_provider_id TEXT NOT NULL DEFAULT '',
  fallback_model_id TEXT NOT NULL DEFAULT '',
  trigger_reason TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  approved_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  rejected_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_fallback_approval_requests_tenant_status
  ON fallback_approval_requests(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_fallback_approval_requests_room
  ON fallback_approval_requests(room_id);
CREATE INDEX IF NOT EXISTS idx_fallback_approval_requests_run
  ON fallback_approval_requests(orchestration_run_id);
