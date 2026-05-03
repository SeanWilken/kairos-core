-- 0015_audit_events.sql
-- Adds compact audit events for orchestration and policy decisions.

CREATE TABLE IF NOT EXISTS audit_events (
  audit_event_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  actor_type TEXT NOT NULL DEFAULT 'system',
  actor_id TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL DEFAULT '',
  resource_id TEXT NOT NULL DEFAULT '',
  room_id TEXT NOT NULL DEFAULT '',
  orchestration_run_id TEXT NOT NULL DEFAULT '',
  decision TEXT NOT NULL DEFAULT 'allowed',
  reason_code TEXT NOT NULL DEFAULT '',
  policy_version TEXT NOT NULL DEFAULT 'v1',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_created
  ON audit_events(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_room
  ON audit_events(room_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_run
  ON audit_events(orchestration_run_id);
