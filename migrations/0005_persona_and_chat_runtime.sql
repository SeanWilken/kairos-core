-- 0005_persona_and_chat_runtime.sql
-- Adds persona storage and chat runtime metadata.

CREATE TABLE IF NOT EXISTS studio_personas (
  persona_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  role TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'organization',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  model_profile TEXT NOT NULL DEFAULT 'reasoning-optimized',
  system_prompt TEXT NOT NULL DEFAULT '',
  persona_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_personas_org_slug UNIQUE (org_id, slug)
);

ALTER TABLE studio_channels
  ADD COLUMN IF NOT EXISTS response_policy TEXT NOT NULL DEFAULT 'single_best';

ALTER TABLE studio_channels
  ADD COLUMN IF NOT EXISTS auto_respond BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE studio_channels
  ADD COLUMN IF NOT EXISTS responder_delay_seconds INTEGER NOT NULL DEFAULT 12;

ALTER TABLE studio_channels
  ADD COLUMN IF NOT EXISTS default_persona_id TEXT NULL;

ALTER TABLE studio_channel_messages
  ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_studio_personas_org ON studio_personas(org_id);
