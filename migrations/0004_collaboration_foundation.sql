-- 0004_collaboration_foundation.sql
-- Adds divisions, teams, channels, messages, and tasks.

CREATE TABLE IF NOT EXISTS studio_divisions (
  division_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_divisions_org_slug UNIQUE (org_id, slug)
);

CREATE TABLE IF NOT EXISTS studio_teams (
  team_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  division_id TEXT NULL REFERENCES studio_divisions(division_id) ON DELETE SET NULL,
  parent_team_id TEXT NULL REFERENCES studio_teams(team_id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  access_mode TEXT NOT NULL DEFAULT 'internal',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_teams_org_slug UNIQUE (org_id, slug)
);

CREATE TABLE IF NOT EXISTS studio_team_memberships (
  team_membership_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  team_id TEXT NOT NULL REFERENCES studio_teams(team_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_team_memberships_team_user UNIQUE (team_id, user_id)
);

CREATE TABLE IF NOT EXISTS studio_channels (
  channel_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  team_id TEXT NULL REFERENCES studio_teams(team_id) ON DELETE SET NULL,
  channel_type TEXT NOT NULL,
  name TEXT NOT NULL,
  retention_days INTEGER NOT NULL DEFAULT 90,
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS studio_channel_participants (
  participant_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  channel_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  joined_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_channel_participants_channel_user UNIQUE (channel_id, user_id)
);

CREATE TABLE IF NOT EXISTS studio_channel_messages (
  message_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  channel_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
  sender_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS studio_tasks (
  task_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  team_id TEXT NULL REFERENCES studio_teams(team_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'todo',
  visibility TEXT NOT NULL DEFAULT 'team_public',
  owner_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS studio_task_assignments (
  assignment_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  task_id TEXT NOT NULL REFERENCES studio_tasks(task_id) ON DELETE CASCADE,
  assignee_user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_studio_task_assignments_task_user UNIQUE (task_id, assignee_user_id)
);

CREATE INDEX IF NOT EXISTS idx_studio_divisions_org ON studio_divisions(org_id);
CREATE INDEX IF NOT EXISTS idx_studio_teams_org ON studio_teams(org_id);
CREATE INDEX IF NOT EXISTS idx_studio_teams_division ON studio_teams(division_id);
CREATE INDEX IF NOT EXISTS idx_studio_teams_parent ON studio_teams(parent_team_id);
CREATE INDEX IF NOT EXISTS idx_studio_team_memberships_team ON studio_team_memberships(team_id);
CREATE INDEX IF NOT EXISTS idx_studio_channels_org ON studio_channels(org_id);
CREATE INDEX IF NOT EXISTS idx_studio_channels_team ON studio_channels(team_id);
CREATE INDEX IF NOT EXISTS idx_studio_channel_messages_channel ON studio_channel_messages(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_studio_tasks_org ON studio_tasks(org_id);
CREATE INDEX IF NOT EXISTS idx_studio_tasks_team ON studio_tasks(team_id);
CREATE INDEX IF NOT EXISTS idx_studio_tasks_owner ON studio_tasks(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_studio_task_assignments_task ON studio_task_assignments(task_id);
