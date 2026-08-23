from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_knowledge_index_domain_node_edge_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="knowledge.owner@myai.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Knowledge Org", "slug": "knowledge-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]
    headers["X-Org-ID"] = org_id

    domain = client.post(
        "/v1/knowledge/domains",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Billing",
            "summary": "Billing and refund knowledge",
            "sensitivity_default": "internal",
            "tags": ["billing", "refund"],
        },
    )
    assert domain.status_code == 200
    domain_id = domain.json()["data"]["domain_id"]

    node_a = client.post(
        "/v1/knowledge/nodes",
        headers=headers,
        json={
            "org_id": org_id,
            "domain_id": domain_id,
            "node_type": "document",
            "title": "Enterprise Refund Policy",
            "summary": "Refund policy for enterprise plans",
            "sensitivity": "restricted",
            "source_type": "document",
            "source_id": "doc-refund-1",
        },
    )
    assert node_a.status_code == 200
    node_a_id = node_a.json()["data"]["node_id"]

    node_b = client.post(
        "/v1/knowledge/nodes",
        headers=headers,
        json={
            "org_id": org_id,
            "domain_id": domain_id,
            "node_type": "faq_entry",
            "title": "Support Refund FAQ",
            "summary": "Customer-facing refund FAQ",
            "sensitivity": "public",
            "source_type": "faq",
            "source_id": "faq-refund-1",
        },
    )
    assert node_b.status_code == 200
    node_b_id = node_b.json()["data"]["node_id"]

    edge = client.post(
        "/v1/knowledge/edges",
        headers=headers,
        json={
            "org_id": org_id,
            "from_node_id": node_b_id,
            "to_node_id": node_a_id,
            "relationship_type": "derived_from",
            "summary": "FAQ derived from policy",
            "visibility": "internal",
            "confidence": 0.9,
        },
    )
    assert edge.status_code == 200

    list_domains = client.get(f"/v1/knowledge/domains?org_id={org_id}", headers=headers)
    assert list_domains.status_code == 200
    assert len(list_domains.json()["data"]["items"]) == 1

    list_nodes = client.get(f"/v1/knowledge/nodes?org_id={org_id}&domain_id={domain_id}", headers=headers)
    assert list_nodes.status_code == 200
    assert len(list_nodes.json()["data"]["items"]) == 2

    list_edges = client.get(f"/v1/knowledge/edges?org_id={org_id}&node_id={node_b_id}", headers=headers)
    assert list_edges.status_code == 200
    assert len(list_edges.json()["data"]["items"]) == 1


def test_knowledge_index_rejects_cross_org_mutable_scope() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="knowledge.scope.admin@myai.dev")

    org_ids = []
    for name, slug in (("Knowledge Scope A", "knowledge-scope-a"), ("Knowledge Scope B", "knowledge-scope-b")):
        response = client.post(
            "/v1/studio/organizations",
            headers=admin_headers,
            json={"name": name, "slug": slug, "mode": "team"},
        )
        assert response.status_code == 200
        org_ids.append(response.json()["data"]["org_id"])
    org_a_id, org_b_id = org_ids

    unscoped_global_write = client.post(
        "/v1/knowledge/nodes",
        headers=admin_headers,
        json={"org_id": org_b_id, "node_type": "document", "title": "Unscoped global write"},
    )
    assert unscoped_global_write.status_code == 403
    assert unscoped_global_write.json()["error"]["details"]["reason_code"] == "ORG_SCOPE_FORBIDDEN"

    org_b_headers = {**admin_headers, "X-Org-ID": org_b_id}
    node_b = client.post(
        "/v1/knowledge/nodes",
        headers=org_b_headers,
        json={"org_id": org_b_id, "node_type": "document", "title": "Org B private node"},
    )
    assert node_b.status_code == 200

    org_a_headers = register_and_login(
        client,
        email="knowledge.scope.a@myai.dev",
        org_id=org_a_id,
        is_global_admin=False,
    )
    write_node = client.post(
        "/v1/knowledge/nodes",
        headers=org_a_headers,
        json={"org_id": org_b_id, "node_type": "document", "title": "Cross-org node"},
    )
    assert write_node.status_code == 403
    assert write_node.json()["error"]["details"]["reason_code"] == "ORG_SCOPE_FORBIDDEN"

    write_edge = client.post(
        "/v1/knowledge/edges",
        headers=org_a_headers,
        json={
            "org_id": org_b_id,
            "from_node_id": node_b.json()["data"]["node_id"],
            "to_node_id": node_b.json()["data"]["node_id"],
            "relationship_type": "related_to",
        },
    )
    assert write_edge.status_code == 403

    for resource in ("domains", "nodes", "edges"):
        response = client.get(
            f"/v1/knowledge/{resource}",
            headers=org_a_headers,
            params={"org_id": org_b_id},
        )
        assert response.status_code == 403
        assert response.json()["error"]["details"]["reason_code"] == "ORG_SCOPE_FORBIDDEN"
