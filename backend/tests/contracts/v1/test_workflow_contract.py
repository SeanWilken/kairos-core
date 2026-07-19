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


def test_workflow_graph_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="workflow.graph@myai.dev",
        org_name="Workflow Graph Org",
        org_slug="workflow-graph-org",
    )

    create_response = client.post(
        "/v1/studio/workflows",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Deployment Workflow",
            "description": "Deployment flow with review gate",
            "trigger": {"type": "manual"},
            "nodes": [
                {"node_id": "n1", "kind": "document_draft", "label": "Draft Guide", "config": {}},
                {"node_id": "n2", "kind": "review_gate", "label": "Review", "config": {}},
            ],
            "edges": [
                {"edge_id": "e1", "from_node_id": "n1", "to_node_id": "n2", "relationship_type": "next"}
            ],
            "logic_rules": [
                {
                    "rule_id": "r1",
                    "scope": "workflow",
                    "trigger": "after_node:n1",
                    "condition": {"type": "tag_present", "config": {"value": "deployment"}},
                    "action": {"type": "require_review", "reason": "deployment_review", "config": {}},
                    "priority": 10,
                }
            ],
            "policy": {"retry_count": 0, "timeout_seconds": 60, "failure_mode": "manual_review"},
            "metadata": {"source": "test"},
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    workflow_id = created["workflow_id"]
    assert created["name"] == "Deployment Workflow"
    assert len(created["nodes"]) == 2

    list_response = client.get(
        "/v1/studio/workflows",
        headers=headers,
        params={"org_id": org_id},
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert any(item["workflow_id"] == workflow_id for item in items)

    get_response = client.get(f"/v1/studio/workflows/{workflow_id}", headers=headers)
    assert get_response.status_code == 200
    fetched = get_response.json()["data"]
    assert fetched["workflow_id"] == workflow_id

    patch_response = client.patch(
        f"/v1/studio/workflows/{workflow_id}",
        headers=headers,
        json={"description": "Updated description"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["description"] == "Updated description"

    run_start = client.post(
        f"/v1/studio/workflows/{workflow_id}/runs",
        headers=headers,
        json={
            "artifact": {
                "kind": "knowledge_node",
                "tags": ["deployment"],
                "summary": "Deployment draft",
                "visibility": {"scope": "org"},
                "facets": {},
                "kind_payload": {"content": "Deployment notes"},
                "quality": {},
            },
            "review_context": {"requested_by": "test", "node_id": "n2", "title": "Deployment Review", "summary": "Review deployment artifact"},
        },
    )
    assert run_start.status_code == 200
    run_start_data = run_start.json()["data"]
    assert run_start_data["run"]["status"] == "paused_review"
    assert run_start_data["current_node_id"] == "n2"
    assert len(run_start_data["execution_trace"]) >= 2

    dry_run = client.post(
        f"/v1/studio/workflows/{workflow_id}/dry-run",
        headers=headers,
        json={
            "artifact": {
                "kind": "knowledge_node",
                "tags": ["deployment"],
                "summary": "Deployment draft",
                "visibility": {"scope": "org"},
                "facets": {},
                "kind_payload": {"content": "Deployment notes"},
                "quality": {},
            },
            "review_context": {"requested_by": "test", "node_id": "n2", "title": "Deployment Review", "summary": "Review deployment artifact"},
        },
    )
    assert dry_run.status_code == 200
    dry_data = dry_run.json()["data"]
    assert dry_data["review_required"] is True
    assert dry_data["blocked"] is False
    assert dry_data["run"]["status"] == "paused_review"
    assert dry_data["review_item"]["status"] == "pending"
    run_id = dry_data["run"]["run_id"]
    review_id = dry_data["review_item"]["review_id"]

    runs_response = client.get(f"/v1/studio/workflows/{workflow_id}/runs", headers=headers)
    assert runs_response.status_code == 200
    runs = runs_response.json()["data"]["items"]
    assert any(item["run_id"] == run_id for item in runs)

    run_response = client.get(f"/v1/studio/workflow-runs/{run_id}", headers=headers)
    assert run_response.status_code == 200
    assert run_response.json()["data"]["status"] == "paused_review"

    reviews_response = client.get("/v1/studio/workflow-reviews", headers=headers, params={"org_id": org_id, "status": "pending"})
    assert reviews_response.status_code == 200
    reviews = reviews_response.json()["data"]["items"]
    assert any(item["review_id"] == review_id for item in reviews)

    decision_response = client.post(
        f"/v1/studio/workflow-reviews/{review_id}/decision",
        headers=headers,
        json={"decision": "approve"},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["data"]["status"] == "approved"

    run_after = client.get(f"/v1/studio/workflow-runs/{run_id}", headers=headers)
    assert run_after.status_code == 200
    assert run_after.json()["data"]["status"] == "completed"
