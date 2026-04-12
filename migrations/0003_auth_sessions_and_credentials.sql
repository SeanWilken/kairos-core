-- 0003_auth_sessions_and_credentials.sql
-- Adds password credential storage and refresh token sessions.

CREATE TABLE IF NOT EXISTS studio_user_credentials (
  user_id TEXT PRIMARY KEY REFERENCES studio_users(user_id) ON DELETE CASCADE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
  token_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL DEFAULT '',
  token_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_auth_refresh_tokens_hash UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_user ON auth_refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_tenant ON auth_refresh_tokens (tenant_id);
