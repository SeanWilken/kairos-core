from fastapi.testclient import TestClient

from app.main import app

def test_protected_ping_success_uses_v1_envelope_contract() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Tenant-ID": "tenant0", "X-Org-ID": "org0", "X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert isinstance(body["meta"]["service"], str) 
    assert isinstance(body["meta"]["version"], str)  
    assert body["meta"]["spec_version"] == "v1"
    assert isinstance(body["meta"]["environment"], str) 
    assert isinstance(body["meta"]["timestamp"], str)
    assert isinstance(body["meta"]["correlation_id"], str)
    assert body["meta"]["correlation_id"] == "test-correlation-id"

def test_protected_ping_failed_org_uses_v1_envelope_contract() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Tenant-ID": "tenant0", "X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 403
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert isinstance(body["meta"]["service"], str)
    assert isinstance(body["meta"]["version"], str) 
    assert body["meta"]["spec_version"] == "v1"
    assert isinstance(body["meta"]["environment"], str) 
    assert isinstance(body["meta"]["timestamp"], str)
    assert isinstance(body["meta"]["correlation_id"], str)
    assert body["data"] is None
    assert body["error"]["message"] == "Organization context is required."
    assert body["error"]["details"]["reason_code"] == "ORG_CONTEXT_MISSING"

def test_protected_ping_failed_tenant_uses_v1_envelope_contract() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Org-ID": "org0", "X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 403
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert isinstance(body["meta"]["service"], str)
    assert isinstance(body["meta"]["version"], str) 
    assert body["meta"]["spec_version"] == "v1"
    assert isinstance(body["meta"]["environment"], str) 
    assert isinstance(body["meta"]["timestamp"], str)
    assert isinstance(body["meta"]["correlation_id"], str)
    assert body["data"] is None
    assert body["error"]["message"] == "Tenant context is required."
    assert body["error"]["details"]["reason_code"] == "TENANT_CONTEXT_MISSING"
