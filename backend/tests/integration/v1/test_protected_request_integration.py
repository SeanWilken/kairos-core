from fastapi.testclient import TestClient

from app.main import app

def test_protected_ping_success_uses_v1_envelope_integration() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Tenant-ID": "tenant0", "X-Org-ID": "org0", "X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 200
    body = response.json()
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"
    assert body["error"] is None
    assert body["data"].get("message") == "Protected pong."

def test_protected_ping_missing_tenant_uses_access_denied_integration() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Org-ID": "org0", "X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "ACCESS_DENIED"
    assert body["error"]["details"]["reason_code"] == "TENANT_CONTEXT_MISSING"
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"

def test_protected_ping_missing_org_uses_access_denied_integration() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Tenant-ID": "tenant0", "X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "ACCESS_DENIED"
    assert body["error"]["details"]["reason_code"] == "ORG_CONTEXT_MISSING"
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"
