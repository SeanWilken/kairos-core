-- 0016_knowledge_index_foundation.sql
-- Foundational Knowledge Index Hub schema.

CREATE TABLE IF NOT EXISTS knowledge_domains (
  domain_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  parent_domain_id TEXT NULL REFERENCES knowledge_domains(domain_id) ON DELETE SET NULL,
  sensitivity_default TEXT NOT NULL DEFAULT 'internal',
  tags_json TEXT NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_knowledge_domains_name UNIQUE (tenant_id, org_id, name)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_domains_tenant_org
  ON knowledge_domains(tenant_id, org_id);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  node_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  domain_id TEXT NULL REFERENCES knowledge_domains(domain_id) ON DELETE SET NULL,
  node_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]',
  sensitivity TEXT NOT NULL DEFAULT 'internal',
  source_type TEXT NOT NULL DEFAULT '',
  source_id TEXT NOT NULL DEFAULT '',
  owner_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active',
  confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_tenant_org
  ON knowledge_nodes(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_domain
  ON knowledge_nodes(domain_id);

CREATE TABLE IF NOT EXISTS knowledge_edges (
  edge_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  org_id TEXT NOT NULL REFERENCES studio_organizations(org_id) ON DELETE CASCADE,
  from_node_id TEXT NOT NULL REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
  to_node_id TEXT NOT NULL REFERENCES knowledge_nodes(node_id) ON DELETE CASCADE,
  relationship_type TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'internal',
  confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_by_user_id TEXT NULL REFERENCES studio_users(user_id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_knowledge_edges_relation UNIQUE (tenant_id, org_id, from_node_id, to_node_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_edges_tenant_org
  ON knowledge_edges(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_from
  ON knowledge_edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_to
  ON knowledge_edges(to_node_id);
