-- Migration 0009: Prompt Prefabs File: 

CREATE TABLE IF NOT EXISTS prompt_prefabs (
    prefab_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    industry TEXT NOT NULL,
    role TEXT NOT NULL,
    segment_type TEXT NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    variables_json TEXT NOT NULL DEFAULT '{}',
    tokens_estimate INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_prompt_prefabs_tenant_industry_role_segment UNIQUE (tenant_id, industry, role, segment_type, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_prefabs_industry_role ON prompt_prefabs(industry, role);
CREATE INDEX IF NOT EXISTS idx_prompt_prefabs_segment_type ON prompt_prefabs(segment_type);
