CREATE TABLE IF NOT EXISTS studio_notifications (
  notification_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  entity_type TEXT NOT NULL DEFAULT '',
  entity_id TEXT NOT NULL DEFAULT '',
  severity TEXT NOT NULL DEFAULT 'info',
  status TEXT NOT NULL DEFAULT 'unread',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  read_at TIMESTAMPTZ NULL,
  archived_at TIMESTAMPTZ NULL,
  dismissed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_studio_notifications_user_status_created
  ON studio_notifications (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_studio_notifications_tenant_org_kind
  ON studio_notifications (tenant_id, org_id, kind);

CREATE TABLE IF NOT EXISTS studio_message_read_receipts (
  receipt_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  channel_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
  message_id TEXT NOT NULL REFERENCES studio_channel_messages(message_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source TEXT NOT NULL DEFAULT 'ui',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_studio_message_read_receipts_message_user UNIQUE (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_studio_message_read_receipts_channel_user_read_at
  ON studio_message_read_receipts (channel_id, user_id, read_at DESC);

CREATE TABLE IF NOT EXISTS studio_channel_read_state (
  state_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  channel_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  last_read_message_id TEXT NULL REFERENCES studio_channel_messages(message_id) ON DELETE SET NULL,
  last_read_at TIMESTAMPTZ NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_studio_channel_read_state_channel_user UNIQUE (channel_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_studio_channel_read_state_user_updated
  ON studio_channel_read_state (user_id, updated_at DESC);

COMMENT ON TABLE studio_notifications IS 'Per-user notification feed for chat, approvals, tasks, mailbox, diary, and system events.';
COMMENT ON COLUMN studio_notifications.kind IS 'Notification category. Suggested values: chat_message, chat_mention, task_assigned, approval_required, mailbox_ready, diary_ready, system.';
COMMENT ON COLUMN studio_notifications.entity_type IS 'Logical entity type associated with this notification, such as channel, task, run, mailbox_item, or diary_entry.';
COMMENT ON COLUMN studio_notifications.entity_id IS 'Primary identifier for the associated entity_type.';
COMMENT ON COLUMN studio_notifications.severity IS 'Urgency level. Suggested values: info, warning, critical.';
COMMENT ON COLUMN studio_notifications.status IS 'Read lifecycle state. Suggested values: unread, read, archived, dismissed.';
COMMENT ON COLUMN studio_notifications.metadata_json IS 'Extensible JSON metadata for UI rendering, routing, and diagnostics.';

COMMENT ON TABLE studio_message_read_receipts IS 'Per-message per-user read receipts for collaboration channels.';
COMMENT ON COLUMN studio_message_read_receipts.source IS 'Read update source. Suggested values: ui, api, sync, system.';
COMMENT ON COLUMN studio_message_read_receipts.metadata_json IS 'Extensible JSON metadata for read events and diagnostics.';

COMMENT ON TABLE studio_channel_read_state IS 'Per-channel per-user read cursor for efficient unread calculations.';
COMMENT ON COLUMN studio_channel_read_state.last_read_message_id IS 'Most recent message marked as read by this user in the channel.';
COMMENT ON COLUMN studio_channel_read_state.last_read_at IS 'Timestamp corresponding to the latest known read cursor.';
