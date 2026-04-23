from fastapi.testclient import TestClient

from app.main import app


def test_bootstrap_tenant_status_and_create_contract() -> None:
    client = TestClient(app)

    status_before = client.get("/v1/bootstrap/tenant/status")
    assert status_before.status_code == 200
    body_before = status_before.json()
    assert body_before["error"] is None
    assert body_before["data"]["configured"] is False

    created = client.post(
        "/v1/bootstrap/tenant",
        json={"tenant_id": "tenant0", "name": "Tenant Zero"},
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["error"] is None
    assert created_body["data"]["tenant_id"] == "tenant0"

    status_after = client.get("/v1/bootstrap/tenant/status")
    assert status_after.status_code == 200
    body_after = status_after.json()
    assert body_after["error"] is None
    assert body_after["data"]["configured"] is True
    assert body_after["data"]["tenant"]["tenant_id"] == "tenant0"


def test_bootstrap_tenant_conflict_when_already_configured_contract() -> None:
    client = TestClient(app)
    first = client.post(
        "/v1/bootstrap/tenant",
        json={"tenant_id": "tenant0", "name": "Tenant Zero"},
    )
    assert first.status_code == 200

    second = client.post(
        "/v1/bootstrap/tenant",
        json={"tenant_id": "tenant1", "name": "Tenant One"},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["details"]["reason_code"] == "TENANT_ALREADY_CONFIGURED"
