-- 0023_tasks_and_meetings_context.sql

ALTER TABLE studio_tasks ADD COLUMN IF NOT EXISTS tags_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE studio_tasks ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE studio_tasks ADD COLUMN IF NOT EXISTS related_node_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE studio_tasks ADD COLUMN IF NOT EXISTS channel_id TEXT NULL REFERENCES studio_channels(channel_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_studio_tasks_channel_id ON studio_tasks(channel_id);

CREATE TABLE IF NOT EXISTS studio_meetings (
  meeting_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  team_id TEXT NULL REFERENCES studio_teams(team_id) ON DELETE SET NULL,
  channel_id TEXT NULL REFERENCES studio_channels(channel_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'scheduled',
  scheduled_start_at TIMESTAMPTZ NOT NULL,
  scheduled_end_at TIMESTAMPTZ NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'UTC',
  tags_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  agenda_json TEXT NOT NULL DEFAULT '[]',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_studio_meetings_tenant_org ON studio_meetings(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_studio_meetings_time ON studio_meetings(scheduled_start_at, scheduled_end_at);
CREATE INDEX IF NOT EXISTS idx_studio_meetings_channel ON studio_meetings(channel_id);

CREATE TABLE IF NOT EXISTS studio_meeting_participants (
  participant_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  meeting_id TEXT NOT NULL REFERENCES studio_meetings(meeting_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'attendee',
  status TEXT NOT NULL DEFAULT 'invited',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_studio_meeting_participants_meeting_user UNIQUE (meeting_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_studio_meeting_participants_tenant_meeting ON studio_meeting_participants(tenant_id, meeting_id);
