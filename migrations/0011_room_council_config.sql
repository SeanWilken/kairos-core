-- Migration 0011: Room Council Configuration File: 

CREATE TABLE IF NOT EXISTS room_council_config (
    config_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
    council_head_persona_id TEXT NULL REFERENCES studio_personas(persona_id) ON DELETE SET NULL,
    council_mode TEXT NOT NULL DEFAULT 'summarized',
    delay_before_orchestration_ms INTEGER NOT NULL DEFAULT 10000,
    show_reasoning_metadata BOOLEAN NOT NULL DEFAULT TRUE,
    allow_parallel_responses BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_room_council_config_room UNIQUE (room_id)
);

CREATE TABLE IF NOT EXISTS room_personas (
    room_persona_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES studio_channels(channel_id) ON DELETE CASCADE,
    persona_id TEXT NOT NULL REFERENCES studio_personas(persona_id) ON DELETE CASCADE,
    role_in_room TEXT NOT NULL DEFAULT 'member',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_room_personas_room_persona UNIQUE (room_id, persona_id)
);

CREATE INDEX IF NOT EXISTS idx_room_personas_room ON room_personas(room_id);
CREATE INDEX IF NOT EXISTS idx_room_personas_persona ON room_personas(persona_id);
