-- Migration 0007: Persona Template Options

CREATE TABLE IF NOT EXISTS persona_template_categories (
    category_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_persona_template_categories_tenant_name UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS persona_template_options (
    option_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    category_id TEXT NOT NULL REFERENCES persona_template_categories(category_id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    label TEXT NOT NULL,
    verbose_statement TEXT NOT NULL,
    provider_compatibility_json TEXT NOT NULL DEFAULT '["openai","anthropic"]',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_persona_template_options_category_key UNIQUE (category_id, key)
);

CREATE INDEX IF NOT EXISTS idx_persona_template_options_category ON persona_template_options(category_id);
CREATE INDEX IF NOT EXISTS idx_persona_template_options_tenant ON persona_template_options(tenant_id);
