-- 0013_pack_review_workflow.sql
-- Adds required human-review workflow for community pack imports.

CREATE TABLE IF NOT EXISTS pack_import_queue (
  queue_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  pack_data_json TEXT NOT NULL DEFAULT '{}',
  extracted_config_json TEXT NOT NULL DEFAULT '{}',
  safety_flags_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending_review',
  review_notes TEXT NOT NULL DEFAULT '',
  reviewed_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  installed_persona_id TEXT NULL REFERENCES studio_personas(persona_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_pack_import_queue_status ON pack_import_queue(status);
CREATE INDEX IF NOT EXISTS idx_pack_import_queue_tenant ON pack_import_queue(tenant_id);

CREATE TABLE IF NOT EXISTS pack_review_conversations (
  conversation_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  queue_id TEXT NOT NULL REFERENCES pack_import_queue(queue_id) ON DELETE CASCADE,
  test_case_key TEXT NOT NULL,
  prompt TEXT NOT NULL DEFAULT '',
  response TEXT NOT NULL DEFAULT '',
  passed BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT NOT NULL DEFAULT '',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_pack_review_conversations_queue_case UNIQUE (queue_id, test_case_key)
);

CREATE INDEX IF NOT EXISTS idx_pack_review_conversations_queue ON pack_review_conversations(queue_id);
