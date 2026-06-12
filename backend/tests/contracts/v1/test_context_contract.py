from __future__ import annotations

from datetime import UTC, datetime
import io

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
        "semantic_match",
        "policy_priority",
        "graph_proximity",
        "owner_authority",
        "freshness_boost",
    }
    assert isinstance(first["selection_reason_short"], str)
    assert isinstance(first["primary_path"], list)
    assert len(first["primary_path"]) <= 4


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
