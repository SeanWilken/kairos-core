from __future__ import annotations

from datetime import UTC, datetime
import io
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def _org_headers(client: TestClient, *, email: str, org_name: str, org_slug: str) -> tuple[dict[str, str], str]:
    headers = register_and_login(client, email=email)
    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": org_name, "slug": org_slug, "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]
    scoped = dict(headers)
    scoped["X-Org-ID"] = org_id
    return scoped, org_id


def _entity(entity_id: str, *, kind: str, title: str, visibility: dict[str, str]) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "entity_id": entity_id,
        "kind": kind,
        "kind_schema_version": "v1",
        "title": title,
        "summary": "",
        "tags": ["test"],
        "contexts": ["development"],
        "facets": {},
        "owners": [{"owner_type": "user", "owner_id": "owner"}],
        "visibility": visibility,
        "source": {
            "source_system": "tests",
            "source_id": entity_id,
            "external_ref": "",
            "source_of_truth": True,
            "dedupe_key": entity_id,
        },
        "content_refs": [],
        "quality": {"confidence": 1.0, "verification_state": "verified", "evidence_refs": []},
        "relevancy": {},
        "lifecycle": {"status": "active", "effective_from": None, "effective_to": None, "staleness_ttl_seconds": 3600},
        "timestamps": {
            "created_at": now,
            "updated_at": now,
            "observed_at": now,
            "effective_from": None,
            "effective_to": None,
        },
        "kind_payload": {},
        "schema_version": "v1",
    }


def test_context_entities_upsert_rejects_missing_observed_at_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.missing.observed@myai.dev",
        org_name="Context Missing Observed",
        org_slug="context-missing-observed",
    )
    item = _entity(
        "ent-missing-observed",
        kind="document",
        title="Missing Observed",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    del item["timestamps"]["observed_at"]

    response = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [item]},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "KNOWLEDGE_ENTITY_OBSERVED_AT_REQUIRED"


def test_context_resolve_non_debug_payload_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.resolve@myai.dev",
        org_name="Context Resolve",
        org_slug="context-resolve",
    )

    entity_a = _entity(
        "ent-anchor",
        kind="project",
        title="MyAIDE Project",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    entity_b = _entity(
        "ent-task",
        kind="task",
        title="Integrate Resolver",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )

    upsert_entities = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [entity_a, entity_b]},
    )
    assert upsert_entities.status_code == 200

    now = datetime.now(UTC).isoformat()
    relationship = {
        "relationship_id": "rel-anchor-task",
        "from_entity_id": "ent-anchor",
        "to_entity_id": "ent-task",
        "relationship_type": "contains",
        "directionality": "directed",
        "weight": 1.0,
        "facets": {},
        "evidence": [],
        "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
        "source": {"source_system": "tests", "source_id": "rel-anchor-task", "source_of_truth": True},
        "timestamps": {
            "created_at": now,
            "updated_at": now,
            "observed_at": now,
            "effective_from": None,
            "effective_to": None,
        },
        "schema_version": "v1",
    }
    upsert_relationships = client.post(
        "/v1/knowledge/relationships/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [relationship]},
    )
    assert upsert_relationships.status_code == 200

    resolve = client.post(
        "/v1/context/resolve",
        headers=headers,
        json={
            "anchor": {"entity_id": "ent-anchor", "text": "resolver integration"},
            "lens": {
                "include_node_kinds": ["project", "task"],
                "include_relationship_types": ["contains"],
            },
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
            "options": {"include_exclusion_report": False},
        },
    )
    assert resolve.status_code == 200
    data = resolve.json()["data"]
    assert isinstance(data["bundle_id"], str)
    assert isinstance(data["graph_version"], str)
    assert isinstance(data["sources"], list)
    assert len(data["sources"]) >= 1
    first = data["sources"][0]
    assert isinstance(first["entity_id"], str)
    assert isinstance(first["score"], float)
    assert first["selection_reason_code"] in {
        "explicit_reference",
        "semantic_match",
        "policy_priority",
        "graph_proximity",
        "owner_authority",
        "freshness_boost",
    }
    assert isinstance(first["selection_reason_short"], str)
    assert isinstance(first["primary_path"], list)
    assert len(first["primary_path"]) <= 4


def test_context_resolve_relevancy_focus_biases_selection() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.resolve.relevancy@myai.dev",
        org_name="Context Resolve Relevancy",
        org_slug="context-resolve-relevancy",
    )

    entity_a = _entity(
        "ent-backend",
        kind="document",
        title="Backend Service Notes",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    entity_a["relevancy"] = {"backend": {"score": 95, "confidence": 90, "assignedBy": "human"}}
    entity_b = _entity(
        "ent-frontend",
        kind="document",
        title="Frontend Styling Notes",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    entity_b["relevancy"] = {"frontend": {"score": 95, "confidence": 90, "assignedBy": "human"}}

    upsert_entities = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [entity_a, entity_b]},
    )
    assert upsert_entities.status_code == 200

    resolve = client.post(
        "/v1/context/resolve",
        headers=headers,
        json={
            "anchor": {"text": "notes"},
            "lens": {
                "include_node_kinds": ["document"],
                "relevancy_focus": {"backend": 1.0},
            },
            "budget": {"max_nodes": 5, "max_edges": 5, "max_snippets": 5, "max_tokens": 2000},
        },
    )
    assert resolve.status_code == 200
    sources = resolve.json()["data"]["sources"]
    assert sources[0]["entity_id"] == "ent-backend"


def test_context_artifact_promotion_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.artifact.promote@myai.dev",
        org_name="Context Artifact Promote",
        org_slug="context-artifact-promote",
    )

    base_entity = _entity(
        "ent-related-task",
        kind="task",
        title="Related Task",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    upsert_entities = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [base_entity]},
    )
    assert upsert_entities.status_code == 200

    promoted = client.post(
        "/v1/knowledge/artifacts/promote",
        headers=headers,
        json={
            "org_id": org_id,
            "artifact_kind": "knowledge_node",
            "artifact_subtype": "conversation_block",
            "title": "Useful deployment answer",
            "summary": "Promoted from chat",
            "content": "## Deployment Notes\n- refresh image\n- verify health",
            "tags": ["deployment", "chat"],
            "contexts": ["operations"],
            "relevancy": {"backend": {"score": 88, "confidence": 80, "assignedBy": "human"}},
            "relationships": [
                {
                    "target_entity_id": "ent-related-task",
                    "relationship_type": "supports",
                }
            ],
        },
    )
    assert promoted.status_code == 200
    body = promoted.json()["data"]
    artifact = body["artifact"]
    assert artifact["kind"] == "knowledge_node"
    assert artifact["facets"]["subtype"] == "conversation_block"
    assert artifact["relevancy"]["backend"]["score"] == 88
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["relationship_type"] == "supports"


def test_context_artifact_rule_evaluation_contract() -> None:
    client = TestClient(app)
    headers, _org_id = _org_headers(
        client,
        email="context.artifact.rules@myai.dev",
        org_name="Context Artifact Rules",
        org_slug="context-artifact-rules",
    )

    response = client.post(
        "/v1/knowledge/artifacts/evaluate-rules",
        headers=headers,
        json={
            "artifact": {
                "kind": "knowledge_node",
                "summary": "Deployment summary",
                "tags": ["deployment"],
                "visibility": {"scope": "org"},
                "relevancy": {"backend": {"score": 92, "confidence": 80, "assignedBy": "human"}},
                "facets": {},
                "kind_payload": {"content": "Deployment notes"},
                "quality": {},
            },
            "rules": [
                {
                    "rule_id": "require-review-for-deployments",
                    "condition": {"type": "tag_present", "config": {"value": "deployment"}},
                    "action": {"type": "require_review", "config": {}, "reason": "deployment_review"},
                    "priority": 10,
                },
                {
                    "rule_id": "tag-backend-hot",
                    "condition": {"type": "relevancy_min", "config": {"dimension": "backend", "value": 90}},
                    "action": {"type": "add_tag", "tag": "hot-backend"},
                    "priority": 20,
                },
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["blocked"] is False
    assert data["review_required"] is True
    artifact = data["artifact"]
    assert "hot-backend" in artifact["tags"]
    assert artifact["quality"]["review_required"] is True


def test_context_artifact_promotion_blocked_by_rule_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.artifact.block@myai.dev",
        org_name="Context Artifact Block",
        org_slug="context-artifact-block",
    )

    response = client.post(
        "/v1/knowledge/artifacts/promote",
        headers=headers,
        json={
            "org_id": org_id,
            "artifact_kind": "knowledge_node",
            "artifact_subtype": "conversation_block",
            "title": "Private legal note",
            "summary": "Sensitive",
            "content": "Do not promote",
            "tags": ["legal"],
            "validation_rules": [
                {
                    "rule_id": "block-legal",
                    "condition": {"type": "tag_present", "config": {"value": "legal"}},
                    "action": {"type": "block"},
                    "priority": 1,
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason_code"] == "ARTIFACT_PROMOTION_BLOCKED"


def test_context_profiles_contract() -> None:
    client = TestClient(app)
    headers, _org_id = _org_headers(
        client,
        email="context.profiles@myai.dev",
        org_name="Context Profiles Org",
        org_slug="context-profiles-org",
    )

    listed = client.get("/v1/context/profiles", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    profile_ids = {item.get("profile_id") for item in items if isinstance(item, dict)}
    assert "help-desk-agent" in profile_ids
    assert "generalist" in profile_ids
    assert "knowledge-librarian" in profile_ids
    assert "document-drafter" in profile_ids
    assert "project-manager" in profile_ids
    assert "scrum-master" in profile_ids

    fetched = client.get("/v1/context/profiles/help-desk-agent", headers=headers)
    assert fetched.status_code == 200
    data = fetched.json()["data"]
    assert data["profile_id"] == "help-desk-agent"
    assert isinstance(data.get("relevancy_focus", {}), dict)
    assert isinstance(data.get("preferred_tools", []), list)
    assert isinstance(data.get("preferred_tool_policies", []), list)
    assert isinstance(data.get("provider_preferences", {}), dict)
    assert data["provider_preferences"]["text_to_speech"]["provider_id"] == "elevenlabs"
    assert data["voice_defaults"]["tone"] == "friendly"


def test_knowledge_conventions_contract() -> None:
    client = TestClient(app)
    headers, _org_id = _org_headers(
        client,
        email="knowledge.conventions@myai.dev",
        org_name="Knowledge Conventions Org",
        org_slug="knowledge-conventions-org",
    )

    response = client.get("/v1/knowledge/conventions", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "file" in data["entity_conventions"]
    assert "symbol" in data["entity_conventions"]
    assert "glossary_term" in data["entity_conventions"]
    assert "should_be_shared" in data["reuse_relationship_types"]


def test_knowledge_entity_convention_validation_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="knowledge.conventions.validate@myai.dev",
        org_name="Knowledge Convention Validate",
        org_slug="knowledge-convention-validate",
    )

    invalid_file = _entity(
        "ent-invalid-file",
        kind="file",
        title="Missing Path",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    invalid_file["facets"] = {}

    response = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [invalid_file]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason_code"] == "KNOWLEDGE_ENTITY_CONVENTION_FACETS_REQUIRED"


def test_knowledge_code_ingest_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="knowledge.code.ingest@myai.dev",
        org_name="Knowledge Code Ingest",
        org_slug="knowledge-code-ingest",
    )

    response = client.post(
        "/v1/knowledge/code-ingest",
        headers=headers,
        json={
            "org_id": org_id,
            "workspace_id": "ws_local_aide",
            "runner_id": "runner_local_01",
            "project": {
                "title": "Project A",
                "project_key": "proj-a",
                "repo_name": "project-a",
                "repo_root": "C:/code/project-a"
            },
            "files": [
                {
                    "path": "src/helpers.py",
                    "language": "python",
                    "snippet": "def normalize_helper(value):\n    return value.strip()",
                    "symbols": [
                        {
                            "name": "normalize_helper",
                            "symbol_kind": "function",
                            "signature": "def normalize_helper(value)",
                            "body_snippet": "return value.strip()",
                            "line_start": 1,
                            "line_end": 2
                        }
                    ]
                },
                {
                    "path": "src/helpers_v2.py",
                    "language": "python",
                    "symbols": [
                        {
                            "name": "normalize_helper_v2",
                            "symbol_kind": "function"
                        }
                    ]
                }
            ],
            "reuse_links": [
                {
                    "from_ref": "src/helpers.py::normalize_helper",
                    "to_ref": "src/helpers_v2.py::normalize_helper_v2",
                    "relationship_type": "should_be_shared",
                    "facets": {"reason": "extract common helper"}
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["workspace_id"] == "ws_local_aide"
    assert data["runner_id"] == "runner_local_01"
    assert data["entities_upserted"] == 5
    assert data["relationships_upserted"] >= 6
    entity_kinds = {item["kind"] for item in data["items"]["entities"]}
    assert "project" in entity_kinds
    assert "file" in entity_kinds
    assert "symbol" in entity_kinds
    rel_types = {item["relationship_type"] for item in data["items"]["relationships"]}
    assert "should_be_shared" in rel_types


def test_context_resolve_profile_id_biases_selection() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.resolve.profile@myai.dev",
        org_name="Context Resolve Profile",
        org_slug="context-resolve-profile",
    )

    entity_a = _entity(
        "ent-helpdesk",
        kind="knowledge_node",
        title="Customer Issue Playbook",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    entity_a["relevancy"] = {"customer_support": {"score": 96, "confidence": 90, "assignedBy": "human"}}
    entity_b = _entity(
        "ent-general-backend",
        kind="knowledge_node",
        title="Backend General Notes",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    entity_b["relevancy"] = {"backend": {"score": 90, "confidence": 90, "assignedBy": "human"}}

    upsert_entities = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [entity_a, entity_b]},
    )
    assert upsert_entities.status_code == 200

    resolve = client.post(
        "/v1/context/resolve",
        headers=headers,
        json={
            "anchor": {"text": "playbook notes"},
            "lens": {
                "profile_id": "help-desk-agent",
                "include_node_kinds": ["knowledge_node"],
            },
            "budget": {"max_nodes": 5, "max_edges": 5, "max_snippets": 5, "max_tokens": 2000},
        },
    )
    assert resolve.status_code == 200
    sources = resolve.json()["data"]["sources"]
    assert sources[0]["entity_id"] == "ent-helpdesk"


def test_context_resolve_cross_project_reuse_links_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.resolve.reuse@myai.dev",
        org_name="Context Resolve Reuse",
        org_slug="context-resolve-reuse",
    )

    project_a = _entity("ent-project-a", kind="project", title="Project A", visibility={"scope": "org", "acl_policy_id": "policy-org"})
    project_a["facets"] = {"project_key": "proj-a", "repo_name": "project-a"}
    project_b = _entity("ent-project-b", kind="project", title="Project B", visibility={"scope": "org", "acl_policy_id": "policy-org"})
    project_b["facets"] = {"project_key": "proj-b", "repo_name": "project-b"}
    symbol_a = _entity("ent-symbol-a", kind="symbol", title="normalize_helper", visibility={"scope": "org", "acl_policy_id": "policy-org"})
    symbol_a["facets"] = {"symbol_name": "normalize_helper", "symbol_kind": "function", "path": "project-a/src/helpers.py"}
    symbol_b = _entity("ent-symbol-b", kind="symbol", title="normalize_helper_v2", visibility={"scope": "org", "acl_policy_id": "policy-org"})
    symbol_b["facets"] = {"symbol_name": "normalize_helper_v2", "symbol_kind": "function", "path": "project-b/src/helpers.py"}

    upsert = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [project_a, project_b, symbol_a, symbol_b]},
    )
    assert upsert.status_code == 200

    now = datetime.now(UTC).isoformat()
    relationships = [
        {
            "relationship_id": "rel-project-a-symbol-a",
            "from_entity_id": "ent-project-a",
            "to_entity_id": "ent-symbol-a",
            "relationship_type": "contains",
            "directionality": "directed",
            "weight": 1.0,
            "facets": {},
            "evidence": [],
            "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
            "source": {"source_system": "tests", "source_id": "rel-project-a-symbol-a", "source_of_truth": True},
            "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
            "schema_version": "v1",
        },
        {
            "relationship_id": "rel-project-b-symbol-b",
            "from_entity_id": "ent-project-b",
            "to_entity_id": "ent-symbol-b",
            "relationship_type": "contains",
            "directionality": "directed",
            "weight": 1.0,
            "facets": {},
            "evidence": [],
            "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
            "source": {"source_system": "tests", "source_id": "rel-project-b-symbol-b", "source_of_truth": True},
            "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
            "schema_version": "v1",
        },
        {
            "relationship_id": "rel-symbol-reuse",
            "from_entity_id": "ent-symbol-a",
            "to_entity_id": "ent-symbol-b",
            "relationship_type": "similar_to",
            "directionality": "bidirectional",
            "weight": 1.0,
            "facets": {"reason": "same_normalization_logic"},
            "evidence": [],
            "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
            "source": {"source_system": "tests", "source_id": "rel-symbol-reuse", "source_of_truth": True},
            "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
            "schema_version": "v1",
        },
        {
            "relationship_id": "rel-symbol-share",
            "from_entity_id": "ent-symbol-b",
            "to_entity_id": "ent-symbol-a",
            "relationship_type": "should_be_shared",
            "directionality": "directed",
            "weight": 1.0,
            "facets": {"reason": "extract_common_helper"},
            "evidence": [],
            "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
            "source": {"source_system": "tests", "source_id": "rel-symbol-share", "source_of_truth": True},
            "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
            "schema_version": "v1",
        },
    ]
    rel_response = client.post(
        "/v1/knowledge/relationships/upsert",
        headers=headers,
        json={"org_id": org_id, "items": relationships},
    )
    assert rel_response.status_code == 200

    resolve = client.post(
        "/v1/context/resolve",
        headers=headers,
        json={
            "anchor": {"entity_id": "ent-symbol-a", "text": "reuse function `normalize_helper` across projects"},
            "lens": {
                "profile_id": "ai-coding-agent",
                "include_node_kinds": ["project", "symbol"],
                "include_relationship_types": ["contains", "similar_to", "should_be_shared"],
            },
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
        },
    )
    assert resolve.status_code == 200
    data = resolve.json()["data"]
    ids = {item["entity_id"] for item in data["sources"]}
    assert "ent-symbol-a" in ids
    assert "ent-symbol-b" in ids
    assert "ent-project-a" in ids or "ent-project-b" in ids
    code_ids = {item["entity_id"] for item in data["reference_maps"]["code"]}
    assert "ent-symbol-a" in code_ids
    assert "ent-symbol-b" in code_ids


def test_context_resolve_builds_reference_maps_and_compacts_duplicates() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.resolve.refs@myai.dev",
        org_name="Context Resolve Refs",
        org_slug="context-resolve-refs",
    )

    file_entity = _entity(
        "ent-file-main",
        kind="file",
        title="tool_catalog.py",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    file_entity["facets"] = {"path": "backend/app/core/tool_catalog.py"}
    file_entity["content_refs"] = [{"ref_type": "file", "ref": "backend/app/core/tool_catalog.py", "snippet": "def list_tools(): pass", "checksum": ""}]

    duplicate_file_entity = _entity(
        "ent-file-duplicate",
        kind="file",
        title="tool_catalog copy",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    duplicate_file_entity["facets"] = {"path": "backend/app/core/tool_catalog.py"}

    code_entity = _entity(
        "ent-symbol-main",
        kind="symbol",
        title="ToolCatalog",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    code_entity["facets"] = {"symbol_name": "ToolCatalog", "symbol_kind": "class", "path": "backend/app/core/tool_catalog.py"}

    task_entity = _entity(
        "ent-task-ref",
        kind="task",
        title="Unify helper reuse",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    task_entity["summary"] = "Track reuse of helper functions across projects"

    upsert = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [file_entity, duplicate_file_entity, code_entity, task_entity]},
    )
    assert upsert.status_code == 200

    resolve = client.post(
        "/v1/context/explain",
        headers=headers,
        json={
            "anchor": {"text": "reuse `ToolCatalog` in file backend/app/core/tool_catalog.py for task helper-reuse #reuse"},
            "lens": {"include_node_kinds": ["file", "symbol", "task"]},
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 120},
        },
    )
    assert resolve.status_code == 200
    data = resolve.json()["data"]
    assert data["query_signals"]["file_paths"] == ["backend/app/core/tool_catalog.py"]
    assert "files" in data["reference_maps"]
    assert data["reference_maps"]["files"][0]["entity_id"] == "ent-file-main"
    assert "code" in data["reference_maps"]
    assert data["reference_maps"]["code"][0]["entity_id"] == "ent-symbol-main"
    assert data["compaction"]["strategy"] == "deterministic_prune_compact_v1"
    exclusions = data.get("exclusion_report", [])
    assert any(item.get("entity_id") == "ent-file-duplicate" and item.get("reason") == "compacted_duplicate" for item in exclusions)


def test_context_explain_reports_edge_acl_denied_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.edge.acl@myai.dev",
        org_name="Context Edge ACL",
        org_slug="context-edge-acl",
    )

    entities = [
        _entity("ent-a", kind="project", title="A", visibility={"scope": "org", "acl_policy_id": "policy-org"}),
        _entity("ent-b", kind="task", title="B", visibility={"scope": "org", "acl_policy_id": "policy-org"}),
        _entity("ent-c", kind="task", title="C", visibility={"scope": "org", "acl_policy_id": "policy-org"}),
    ]
    upsert_entities = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": entities},
    )
    assert upsert_entities.status_code == 200

    now = datetime.now(UTC).isoformat()
    rel_allowed = {
        "relationship_id": "rel-a-c",
        "from_entity_id": "ent-a",
        "to_entity_id": "ent-c",
        "relationship_type": "contains",
        "directionality": "directed",
        "weight": 1.0,
        "facets": {},
        "evidence": [],
        "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
        "source": {"source_system": "tests", "source_id": "rel-a-c", "source_of_truth": True},
        "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
        "schema_version": "v1",
    }
    rel_denied = {
        "relationship_id": "rel-a-b-denied",
        "from_entity_id": "ent-a",
        "to_entity_id": "ent-b",
        "relationship_type": "contains",
        "directionality": "directed",
        "weight": 1.0,
        "facets": {},
        "evidence": [],
        "visibility": {"scope": "private", "acl_policy_id": "policy-private", "owner_user_id": "someone-else"},
        "source": {"source_system": "tests", "source_id": "rel-a-b-denied", "source_of_truth": True},
        "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
        "schema_version": "v1",
    }
    upsert_relationships = client.post(
        "/v1/knowledge/relationships/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [rel_allowed, rel_denied]},
    )
    assert upsert_relationships.status_code == 200

    explain = client.post(
        "/v1/context/explain",
        headers=headers,
        json={
            "anchor": {"entity_id": "ent-a", "text": "task context"},
            "lens": {
                "include_node_kinds": ["project", "task"],
                "include_relationship_types": ["contains"],
            },
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
        },
    )
    assert explain.status_code == 200
    data = explain.json()["data"]
    reasons = {item["reason"] for item in data.get("exclusion_report", [])}
    assert "edge_acl_denied" in reasons


def test_context_resolve_user_scope_visibility_contract() -> None:
    client = TestClient(app)
    owner_headers, org_id = _org_headers(
        client,
        email="context.user.scope.owner@myai.dev",
        org_name="Context User Scope",
        org_slug="context-user-scope",
    )

    target_headers = register_and_login(
        client,
        email="context.user.scope.target@myai.dev",
        scope_org_id=org_id,
    )
    outsider_headers = register_and_login(
        client,
        email="context.user.scope.outsider@myai.dev",
        scope_org_id=org_id,
    )

    target_user = client.get("/v1/auth/me", headers=target_headers)
    assert target_user.status_code == 200
    target_user_id = target_user.json()["data"]["user"]["user_id"]

    entity_private_to_user = _entity(
        "ent-user-scope",
        kind="document",
        title="User Scoped Doc",
        visibility={"scope": "user", "acl_policy_id": "policy-user", "user_id": target_user_id},
    )
    upsert = client.post(
        "/v1/knowledge/entities/upsert",
        headers=owner_headers,
        json={"org_id": org_id, "items": [entity_private_to_user]},
    )
    assert upsert.status_code == 200

    allowed = client.post(
        "/v1/context/resolve",
        headers=target_headers,
        json={
            "anchor": {"text": "user scoped doc"},
            "lens": {"include_node_kinds": ["document"]},
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
            "options": {"include_exclusion_report": False},
        },
    )
    assert allowed.status_code == 200
    allowed_ids = {item["entity_id"] for item in allowed.json()["data"]["sources"]}
    assert "ent-user-scope" in allowed_ids

    denied = client.post(
        "/v1/context/explain",
        headers=outsider_headers,
        json={
            "anchor": {"text": "user scoped doc"},
            "lens": {"include_node_kinds": ["document"]},
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
        },
    )
    assert denied.status_code == 200
    denied_ids = {item["entity_id"] for item in denied.json()["data"]["sources"]}
    assert "ent-user-scope" not in denied_ids
    exclusions = denied.json()["data"].get("exclusion_report", [])
    assert any(item.get("entity_id") == "ent-user-scope" and item.get("reason") == "acl_denied" for item in exclusions)


def test_context_resolve_team_scope_visibility_contract() -> None:
    client = TestClient(app)
    owner_headers, org_id = _org_headers(
        client,
        email="context.team.scope.owner@myai.dev",
        org_name="Context Team Scope",
        org_slug="context-team-scope",
    )

    member_headers = register_and_login(
        client,
        email="context.team.scope.member@myai.dev",
        scope_org_id=org_id,
    )
    outsider_headers = register_and_login(
        client,
        email="context.team.scope.outsider@myai.dev",
        scope_org_id=org_id,
    )

    member_user = client.get("/v1/auth/me", headers=member_headers)
    assert member_user.status_code == 200
    member_user_id = member_user.json()["data"]["user"]["user_id"]

    create_team = client.post(
        "/v1/studio/teams",
        headers=owner_headers,
        json={"org_id": org_id, "name": "Knowledge Team", "slug": "knowledge-team"},
    )
    assert create_team.status_code == 200
    team_id = create_team.json()["data"]["team_id"]

    add_member = client.post(
        f"/v1/studio/teams/{team_id}/memberships",
        headers=owner_headers,
        json={"user_id": member_user_id, "role": "member", "status": "active"},
    )
    assert add_member.status_code == 200

    team_scoped_entity = _entity(
        "ent-team-scope",
        kind="document",
        title="Team Scoped Doc",
        visibility={"scope": "team", "acl_policy_id": "policy-team", "team_id": team_id},
    )
    upsert_entity = client.post(
        "/v1/knowledge/entities/upsert",
        headers=owner_headers,
        json={"org_id": org_id, "items": [team_scoped_entity]},
    )
    assert upsert_entity.status_code == 200

    team_allowed = client.post(
        "/v1/context/resolve",
        headers=member_headers,
        json={
            "anchor": {"text": "team scoped"},
            "lens": {"include_node_kinds": ["document"]},
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
            "options": {"include_exclusion_report": False},
        },
    )
    assert team_allowed.status_code == 200
    team_allowed_ids = {item["entity_id"] for item in team_allowed.json()["data"]["sources"]}
    assert "ent-team-scope" in team_allowed_ids

    team_denied = client.post(
        "/v1/context/explain",
        headers=outsider_headers,
        json={
            "anchor": {"text": "team scoped"},
            "lens": {"include_node_kinds": ["document"]},
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
        },
    )
    assert team_denied.status_code == 200
    team_denied_ids = {item["entity_id"] for item in team_denied.json()["data"]["sources"]}
    assert "ent-team-scope" not in team_denied_ids
    exclusions = team_denied.json()["data"].get("exclusion_report", [])
    assert any(item.get("entity_id") == "ent-team-scope" and item.get("reason") == "acl_denied" for item in exclusions)


def test_context_document_upload_contract() -> None:
    client = TestClient(app)
    owner_headers, org_id = _org_headers(
        client,
        email="context.upload.owner@myai.dev",
        org_name="Context Upload Org",
        org_slug="context-upload-org",
    )

    upload = client.post(
        "/v1/knowledge/documents/upload",
        headers=owner_headers,
        data={
            "org_id": org_id,
            "title": "Upload Test Doc",
            "summary": "Contract upload test",
            "tags_json": '["docs","upload"]',
            "visibility_json": '{"scope":"org","acl_policy_id":"policy-org"}',
        },
        files={"file": ("notes.txt", io.BytesIO(b"hello knowledge"), "text/plain")},
    )
    assert upload.status_code == 200
    body = upload.json()["data"]
    assert body["entity"]["kind"] == "document"
    assert isinstance(body["entity"]["entity_id"], str)
    assert body["storage"]["backend"] in {"local", "minio"}
    assert body["storage"]["size_bytes"] > 0
    refs = body["entity"].get("content_refs", [])
    assert isinstance(refs, list)
    assert len(refs) >= 1
    assert "hello knowledge" in refs[0].get("snippet", "")


def test_context_document_list_and_content_contract() -> None:
    client = TestClient(app)
    owner_headers, org_id = _org_headers(
        client,
        email="context.upload.list@myai.dev",
        org_name="Context Upload List Org",
        org_slug="context-upload-list-org",
    )

    upload = client.post(
        "/v1/knowledge/documents/upload",
        headers=owner_headers,
        data={
            "org_id": org_id,
            "title": "CSV Upload Test",
            "summary": "Contract list test",
            "tags_json": '["docs","csv"]',
            "visibility_json": '{"scope":"org","acl_policy_id":"policy-org"}',
        },
        files={"file": ("sample.csv", io.BytesIO(b"name,status\nalpha,ok\n"), "text/csv")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["data"]["entity"]["entity_id"]

    listed = client.get(
        "/v1/knowledge/documents",
        headers=owner_headers,
        params={"org_id": org_id},
    )
    assert listed.status_code == 200
    items = listed.json()["data"].get("items", [])
    assert any(item.get("document_id") == document_id for item in items)

    fetched = client.get(f"/v1/knowledge/documents/{document_id}", headers=owner_headers)
    assert fetched.status_code == 200
    document = fetched.json()["data"]["document"]
    assert document["filename"] == "sample.csv"
    assert document["content_type"] == "text/csv"

    content = client.get(f"/v1/knowledge/documents/{document_id}/content", headers=owner_headers)
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("text/csv")
    assert "inline; filename=\"sample.csv\"" in content.headers.get("content-disposition", "")
    assert b"name,status" in content.content


def test_context_documents_reject_cross_org_mutable_scope() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="context.document.scope.admin@myai.dev")
    org_ids = []
    for name, slug in (("Document Scope A", "document-scope-a"), ("Document Scope B", "document-scope-b")):
        response = client.post(
            "/v1/studio/organizations",
            headers=admin_headers,
            json={"name": name, "slug": slug, "mode": "team"},
        )
        assert response.status_code == 200
        org_ids.append(response.json()["data"]["org_id"])
    org_a_id, org_b_id = org_ids

    org_b_headers = {**admin_headers, "X-Org-ID": org_b_id}
    upload_b = client.post(
        "/v1/knowledge/documents/upload",
        headers=org_b_headers,
        data={"org_id": org_b_id, "title": "Org B private document"},
        files={"file": ("private.txt", io.BytesIO(b"org b private content"), "text/plain")},
    )
    assert upload_b.status_code == 200
    document_b_id = upload_b.json()["data"]["entity"]["entity_id"]

    org_a_headers = register_and_login(
        client,
        email="context.document.scope.a@myai.dev",
        org_id=org_a_id,
        is_global_admin=False,
    )
    cross_upload = client.post(
        "/v1/knowledge/documents/upload",
        headers=org_a_headers,
        data={"org_id": org_b_id, "title": "Cross-org upload"},
        files={"file": ("cross.txt", io.BytesIO(b"must not persist"), "text/plain")},
    )
    assert cross_upload.status_code == 403
    assert cross_upload.json()["error"]["details"]["reason_code"] == "ORG_SCOPE_FORBIDDEN"

    cross_list = client.get(
        "/v1/knowledge/documents",
        headers=org_a_headers,
        params={"org_id": org_b_id},
    )
    assert cross_list.status_code == 403
    assert cross_list.json()["error"]["details"]["reason_code"] == "ORG_SCOPE_FORBIDDEN"

    detail = client.get(f"/v1/knowledge/documents/{document_b_id}", headers=org_a_headers)
    content = client.get(f"/v1/knowledge/documents/{document_b_id}/content", headers=org_a_headers)
    assert detail.status_code == 404
    assert content.status_code == 404


def test_context_document_list_filters_and_cursor_contract() -> None:
    client = TestClient(app)
    owner_headers, org_id = _org_headers(
        client,
        email="context.upload.filters@myai.dev",
        org_name="Context Upload Filters Org",
        org_slug="context-upload-filters-org",
    )

    for title, filename, payload in [
        ("Alpha CSV", "alpha.csv", b"name,status\nalpha,ok\n"),
        ("Beta CSV", "beta.csv", b"name,status\nbeta,ok\n"),
    ]:
        upload = client.post(
            "/v1/knowledge/documents/upload",
            headers=owner_headers,
            data={
                "org_id": org_id,
                "title": title,
                "summary": f"Summary for {title}",
                "tags_json": '["docs","csv"]',
                "visibility_json": '{"scope":"org","acl_policy_id":"policy-org"}',
            },
            files={"file": (filename, io.BytesIO(payload), "text/csv")},
        )
        assert upload.status_code == 200

    filtered = client.get(
        "/v1/knowledge/documents",
        headers=owner_headers,
        params={"org_id": org_id, "source_type": "file", "visibility_scope": "org", "query": "beta"},
    )
    assert filtered.status_code == 200
    filtered_items = filtered.json()["data"]["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["title"] == "Beta CSV"
    assert filtered_items[0]["processing_status"] == "active"

    first_page = client.get(
        "/v1/knowledge/documents",
        headers=owner_headers,
        params={"org_id": org_id, "limit": 1},
    )
    assert first_page.status_code == 200
    first_data = first_page.json()["data"]
    assert len(first_data["items"]) == 1
    assert isinstance(first_data.get("next_cursor"), str)

    second_page = client.get(
        "/v1/knowledge/documents",
        headers=owner_headers,
        params={"org_id": org_id, "limit": 1, "cursor": first_data["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_data = second_page.json()["data"]
    assert len(second_data["items"]) == 1
    assert second_data["items"][0]["document_id"] != first_data["items"][0]["document_id"]


def test_context_knowledge_nodes_list_and_detail_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.nodes.list@myai.dev",
        org_name="Context Nodes Org",
        org_slug="context-nodes-org",
    )

    now = datetime.now(UTC).isoformat()
    entity_id = f"node-voice-{uuid4()}"
    entity = {
        "entity_id": entity_id,
        "kind": "knowledge_node",
        "kind_schema_version": "v1",
        "title": "Voice Transcript Note",
        "summary": "Transcript summary",
        "tags": ["voice", "notes"],
        "contexts": [],
        "facets": {"subtype": "voice_transcript"},
        "owners": [{"owner_type": "user", "owner_id": "owner-1"}],
        "visibility": {"scope": "org", "acl_policy_id": "policy-org"},
        "source": {
            "source_system": "voice_stt",
            "source_id": "meeting-1",
            "external_ref": "local://tenant0/org0/meeting.wav",
            "source_of_truth": True,
            "dedupe_key": "meeting-1",
        },
        "content_refs": [{"ref_type": "uri", "ref": "local://tenant0/org0/meeting.wav", "snippet": "meeting notes transcript", "checksum": ""}],
        "quality": {"confidence": 0.9, "verification_state": "derived", "evidence_refs": []},
        "relevancy": {"backend": {"score": 91, "confidence": 85, "assignedBy": "human"}},
        "lifecycle": {"status": "active", "effective_from": None, "effective_to": None, "staleness_ttl_seconds": 0},
        "timestamps": {"created_at": now, "updated_at": now, "observed_at": now, "effective_from": None, "effective_to": None},
        "kind_payload": {"subtype": "voice_transcript", "transcript": "meeting notes transcript"},
        "schema_version": "v1",
    }
    upsert = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [entity]},
    )
    assert upsert.status_code == 200

    listed = client.get(
        "/v1/knowledge/nodes",
        headers=headers,
        params={"org_id": org_id, "kind": "knowledge_node", "subtype": "voice_transcript", "tag": "voice"},
    )
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert isinstance(items, list)

    fetched = client.get(f"/v1/knowledge/nodes/{entity_id}", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()["data"]
    assert body["entity"]["entity_id"] == entity_id
    assert body["summary"]["subtype"] == "voice_transcript"
    assert body["summary"]["relevancy"]["backend"]["score"] == 91


def test_context_channels_contract() -> None:
    client = TestClient(app)
    headers, _org_id = _org_headers(
        client,
        email="context.channels.owner@myai.dev",
        org_name="Context Channels Org",
        org_slug="context-channels-org",
    )
    response = client.get("/v1/context/channels", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"].get("items", [])
    assert isinstance(items, list)
    ids = {item.get("channel_profile_id") for item in items if isinstance(item, dict)}
    assert "development-default" in ids


def test_context_persona_capabilities_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.persona.capabilities@myai.dev",
        org_name="Context Persona Capabilities Org",
        org_slug="context-persona-capabilities-org",
    )

    created = client.post(
        "/v1/studio/personas",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Code Helper",
            "slug": "code-helper",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "runtime_provider_id": "openai",
            "runtime_model_id": "gpt-4o-mini",
            "data": {
                "assigned_tools": ["knowledge_search", "code_generation"],
                "access_policy": {"visibility": "organization"},
                "voice": {"tone": "warm", "cadence": "measured", "voice_id": "amy"},
            },
        },
    )
    assert created.status_code == 200
    persona_id = created.json()["data"]["persona"]["persona_id"]

    listed = client.get("/v1/context/personas/capabilities", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["data"].get("items", [])
    assert isinstance(items, list)
    assert any(item.get("persona_id") == persona_id for item in items)

    fetched = client.get(f"/v1/context/personas/{persona_id}/capability", headers=headers)
    assert fetched.status_code == 200
    data = fetched.json()["data"]
    assert data["persona_id"] == persona_id
    assert data["runtime"]["provider_id"] == "openai"
    assert data["runtime"]["model_id"] == "gpt-4o-mini"
    assert "knowledge_search" in data.get("tools", [])
    assert data["voice"]["tone"] == "warm"


def test_context_daily_summary_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.daily.summary@myai.dev",
        org_name="Context Daily Summary Org",
        org_slug="context-daily-summary-org",
    )

    task = client.post(
        "/v1/studio/tasks",
        headers=headers,
        json={
            "org_id": org_id,
            "title": "Investigate resolver quality",
            "description": "Daily summary test task",
            "visibility": "team_public",
            "status": "todo",
        },
    )
    assert task.status_code == 200

    summary = client.get("/v1/context/daily-summary", headers=headers)
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["org_id"] == org_id
    assert data["user_id"]
    assert isinstance(data.get("highlights", []), list)
    assert isinstance(data.get("sections", {}), dict)
    assert "tasks" in data["sections"]
    assert isinstance(data.get("journal_entry", {}), dict)
    assert data["journal_entry"].get("date") == data["date"]


def test_context_daily_summary_journal_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.daily.journal@myai.dev",
        org_name="Context Daily Journal Org",
        org_slug="context-daily-journal-org",
    )

    generated = client.get("/v1/context/daily-summary", headers=headers)
    assert generated.status_code == 200
    day = generated.json()["data"]["date"]

    journal = client.get(
        f"/v1/context/daily-summary/journal?org_id={org_id}&start_date={day}&end_date={day}",
        headers=headers,
    )
    assert journal.status_code == 200
    items = journal.json()["data"].get("items", [])
    assert isinstance(items, list)
    assert any(item.get("date") == day for item in items)


def test_context_explain_reports_conflict_lost_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.conflict.lost@myai.dev",
        org_name="Context Conflict Org",
        org_slug="context-conflict-org",
    )

    base = _entity(
        "ent-conflict-a",
        kind="document",
        title="Conflict Doc A",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    alt = _entity(
        "ent-conflict-b",
        kind="document",
        title="Conflict Doc B",
        visibility={"scope": "org", "acl_policy_id": "policy-org"},
    )
    alt["source"]["dedupe_key"] = "same-doc"
    base["source"]["dedupe_key"] = "same-doc"
    base["quality"]["verification_state"] = "verified"
    base["source"]["source_of_truth"] = True
    alt["quality"]["verification_state"] = "inferred"
    alt["source"]["source_of_truth"] = False

    upsert = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": [base, alt]},
    )
    assert upsert.status_code == 200

    explain = client.post(
        "/v1/context/explain",
        headers=headers,
        json={
            "anchor": {"text": "conflict doc"},
            "lens": {"include_node_kinds": ["document"]},
            "budget": {"max_nodes": 10, "max_edges": 10, "max_snippets": 10, "max_tokens": 4000},
        },
    )
    assert explain.status_code == 200
    exclusions = explain.json()["data"].get("exclusion_report", [])
    assert any(item.get("entity_id") == "ent-conflict-b" and item.get("reason") == "conflict_lost" for item in exclusions)


def test_context_explain_reports_budget_exceeded_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.budget@myai.dev",
        org_name="Context Budget Org",
        org_slug="context-budget-org",
    )

    items = [
        _entity(
            f"ent-budget-{index}",
            kind="document",
            title=f"Budget Item {index}",
            visibility={"scope": "org", "acl_policy_id": "policy-org"},
        )
        for index in range(4)
    ]
    upsert = client.post(
        "/v1/knowledge/entities/upsert",
        headers=headers,
        json={"org_id": org_id, "items": items},
    )
    assert upsert.status_code == 200

    explain = client.post(
        "/v1/context/explain",
        headers=headers,
        json={
            "anchor": {"text": "budget item"},
            "lens": {"include_node_kinds": ["document"]},
            "budget": {"max_nodes": 1, "max_edges": 10, "max_snippets": 1, "max_tokens": 4000},
        },
    )
    assert explain.status_code == 200
    exclusions = explain.json()["data"].get("exclusion_report", [])
    reasons = {item.get("reason") for item in exclusions}
    assert "budget_exceeded" in reasons


def test_context_identity_and_policy_decision_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.identity.policy@myai.dev",
        org_name="Context Identity Org",
        org_slug="context-identity-org",
    )

    me = client.get("/v1/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = me.json()["data"]["user"]["user_id"]

    grant = client.post(
        "/v1/studio/app-access-grants",
        headers=headers,
        json={
            "org_id": org_id,
            "user_id": user_id,
            "app_id": "myaide",
            "role": "member",
            "feature_flags": ["myaide:access", "myaide:runtime.execute"],
            "status": "active",
        },
    )
    assert grant.status_code == 200

    identity = client.get(f"/v1/context/identity?org_id={org_id}", headers=headers)
    assert identity.status_code == 200
    identity_data = identity.json()["data"]["identity"]
    assert identity_data["org_id"] == org_id
    assert "myaide" in identity_data["app_access"]

    allowed = client.post(
        "/v1/policy/decision",
        headers=headers,
        json={
            "action": "myaide:runtime.execute",
            "context": {"app_id": "myaide", "org_id": org_id},
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"]["allow"] is True
    assert allowed.json()["data"]["reason_code"] == "POLICY_ALLOW"

    denied = client.post(
        "/v1/policy/decision",
        headers=headers,
        json={
            "action": "myaide:diff.approve",
            "context": {"app_id": "myaide", "org_id": org_id},
        },
    )
    assert denied.status_code == 200
    assert denied.json()["data"]["allow"] is False
    assert denied.json()["data"]["reason_code"] == "POLICY_CAPABILITY_DENIED"


def test_context_event_ingest_and_query_contract() -> None:
    client = TestClient(app)
    headers, _org_id = _org_headers(
        client,
        email="context.events@myai.dev",
        org_name="Context Events Org",
        org_slug="context-events-org",
    )

    ingested = client.post(
        "/v1/events/ingest",
        headers=headers,
        json={
            "app_id": "myaide",
            "event_name": "runtime.execute.requested",
            "resource_type": "workspace",
            "resource_id": "ws-123",
            "workspace_id": "ws-123",
            "correlation_id": "corr-abc",
            "metadata": {"prompt_kind": "coding"},
        },
    )
    assert ingested.status_code == 200

    events = client.get(
        "/v1/events?app_id=myaide&workspace_id=ws-123&correlation_id=corr-abc",
        headers=headers,
    )
    assert events.status_code == 200
    items = events.json()["data"].get("items", [])
    assert isinstance(items, list)
    assert any(item.get("action") == "runtime.execute.requested" for item in items)


def test_context_event_stream_contract() -> None:
    client = TestClient(app)
    headers, _org_id = _org_headers(
        client,
        email="context.events.stream@myai.dev",
        org_name="Context Events Stream Org",
        org_slug="context-events-stream-org",
    )

    ingested = client.post(
        "/v1/events/ingest",
        headers=headers,
        json={
            "app_id": "myaide",
            "event_name": "runtime.diff.proposed",
            "resource_type": "workspace",
            "resource_id": "ws-stream",
            "workspace_id": "ws-stream",
            "correlation_id": "corr-stream",
            "metadata": {"kind": "diff"},
        },
    )
    assert ingested.status_code == 200

    stream = client.get(
        "/v1/events/stream?app_id=myaide&workspace_id=ws-stream&correlation_id=corr-stream",
        headers=headers,
    )
    assert stream.status_code == 200
    assert stream.headers.get("content-type", "").startswith("text/event-stream")
    assert "event: canonical_event" in stream.text
    assert "runtime.diff.proposed" in stream.text


def test_policy_decision_audit_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="context.policy.audit@myai.dev",
        org_name="Context Policy Audit Org",
        org_slug="context-policy-audit-org",
    )

    decision = client.post(
        "/v1/policy/decision",
        headers=headers,
        json={
            "action": "myaide:runtime.execute",
            "resource": {"type": "workspace", "id": "ws-audit"},
            "context": {"app_id": "myaide", "org_id": org_id},
        },
    )
    assert decision.status_code == 200

    events = client.get("/v1/events?correlation_id=", headers=headers)
    assert events.status_code == 200
    items = events.json()["data"].get("items", [])
    assert any(item.get("action") == "policy.decision.evaluate" for item in items)
