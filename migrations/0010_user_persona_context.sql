-- Migration 0010: User Persona Context File: 

CREATE TABLE IF NOT EXISTS user_persona_contexts (
    context_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES studio_users(user_id) ON DELETE CASCADE,
    persona_id TEXT NOT NULL REFERENCES studio_personas(persona_id) ON DELETE CASCADE,
    user_strengths_json TEXT NOT NULL DEFAULT '[]',
    user_weaknesses_json TEXT NOT NULL DEFAULT '[]',
    autonomy_level TEXT NOT NULL DEFAULT 'moderate',
    communication_preference TEXT NOT NULL DEFAULT 'balanced',
    detail_level TEXT NOT NULL DEFAULT 'standard',
    check_in_frequency TEXT NOT NULL DEFAULT 'as_needed',
    context_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_persona_contexts_user_persona UNIQUE (user_id, persona_id)
);

CREATE INDEX IF NOT EXISTS idx_user_persona_contexts_user ON user_persona_contexts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_persona_contexts_persona ON user_persona_contexts(persona_id);
