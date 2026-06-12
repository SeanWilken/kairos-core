CREATE TABLE IF NOT EXISTS knowledge_entities (
  entity_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  kind_schema_version TEXT NOT NULL DEFAULT 'v1',
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]',
  contexts_json TEXT NOT NULL DEFAULT '[]',
  facets_json TEXT NOT NULL DEFAULT '{}',
  owners_json TEXT NOT NULL DEFAULT '[]',
  visibility_json TEXT NOT NULL DEFAULT '{}',
  source_json TEXT NOT NULL DEFAULT '{}',
  content_refs_json TEXT NOT NULL DEFAULT '[]',
  quality_json TEXT NOT NULL DEFAULT '{}',
  lifecycle_json TEXT NOT NULL DEFAULT '{}',
  kind_payload_json TEXT NOT NULL DEFAULT '{}',
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  effective_from TIMESTAMPTZ NULL,
  effective_to TIMESTAMPTZ NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_entities_tenant_org ON knowledge_entities (tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_entities_kind ON knowledge_entities (kind);

CREATE TABLE IF NOT EXISTS knowledge_relationships (
  relationship_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  from_entity_id TEXT NOT NULL REFERENCES knowledge_entities(entity_id) ON DELETE CASCADE,
  to_entity_id TEXT NOT NULL REFERENCES knowledge_entities(entity_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL,
  directionality TEXT NOT NULL DEFAULT 'directed',
  weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  facets_json TEXT NOT NULL DEFAULT '{}',
  evidence_json TEXT NOT NULL DEFAULT '[]',
  visibility_json TEXT NOT NULL DEFAULT '{}',
  source_json TEXT NOT NULL DEFAULT '{}',
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  effective_from TIMESTAMPTZ NULL,
  effective_to TIMESTAMPTZ NULL,
  schema_version TEXT NOT NULL DEFAULT 'v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_knowledge_relationships_relation UNIQUE (tenant_id, org_id, from_entity_id, to_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_tenant_org ON knowledge_relationships (tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_type ON knowledge_relationships (relationship_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_from_entity ON knowledge_relationships (from_entity_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_to_entity ON knowledge_relationships (to_entity_id);
