-- Migration 0008: Persona Versioning

CREATE TABLE IF NOT EXISTS persona_versions (
    version_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    persona_id TEXT NOT NULL REFERENCES studio_personas(persona_id) ON DELETE CASCADE,
    version_major INTEGER NOT NULL DEFAULT 1,
    version_minor INTEGER NOT NULL DEFAULT 0,
    version_patch INTEGER NOT NULL DEFAULT 0,
    version_string TEXT NOT NULL,
    config_json TEXT NOT NULL,
    generated_prompt TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    change_summary TEXT NOT NULL DEFAULT '',
    created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_persona_versions_persona_version UNIQUE (persona_id, version_major, version_minor, version_patch)
);

CREATE TABLE IF NOT EXISTS persona_version_history (
    history_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    version_id TEXT NOT NULL REFERENCES persona_versions(version_id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_persona_versions_persona ON persona_versions(persona_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_persona_version_history_version ON persona_version_history(version_id);
