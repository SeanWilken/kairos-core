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
