-- 0014_orchestration_runs_and_event_outbox.sql
-- Adds minimal orchestration run and websocket outbox persistence.

CREATE TABLE IF NOT EXISTS conversation_orchestration_runs (
  run_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  room_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
  triggering_message_id TEXT NULL REFERENCES studio_channel_messages(message_id) ON DELETE SET NULL,
  parent_run_id TEXT NULL REFERENCES conversation_orchestration_runs(run_id) ON DELETE SET NULL,
  source_run_id TEXT NULL REFERENCES conversation_orchestration_runs(run_id) ON DELETE SET NULL,
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  orchestration_type TEXT NOT NULL DEFAULT 'single_best',
  mode TEXT NOT NULL DEFAULT 'single_best',
  status TEXT NOT NULL DEFAULT 'queued',
  client_message_id TEXT NOT NULL DEFAULT '',
  idempotency_key TEXT NOT NULL DEFAULT '',
  failure_reason TEXT NOT NULL DEFAULT '',
  total_input_tokens INTEGER NOT NULL DEFAULT 0,
  total_output_tokens INTEGER NOT NULL DEFAULT 0,
  total_cost_estimate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ NULL,
  completed_at TIMESTAMPTZ NULL,
  failed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_orchestration_runs_tenant_room
  ON conversation_orchestration_runs(tenant_id, room_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_runs_status
  ON conversation_orchestration_runs(status);
CREATE INDEX IF NOT EXISTS idx_orchestration_runs_idempotency
  ON conversation_orchestration_runs(idempotency_key);

CREATE TABLE IF NOT EXISTS event_outbox (
  outbox_event_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  room_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
  orchestration_run_id TEXT NULL REFERENCES conversation_orchestration_runs(run_id) ON DELETE SET NULL,
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  delivered_at TIMESTAMPTZ NULL,
  CONSTRAINT uq_event_outbox_tenant_room_sequence UNIQUE (tenant_id, room_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_event_outbox_tenant_room
  ON event_outbox(tenant_id, room_id);
CREATE INDEX IF NOT EXISTS idx_event_outbox_run
  ON event_outbox(orchestration_run_id);
