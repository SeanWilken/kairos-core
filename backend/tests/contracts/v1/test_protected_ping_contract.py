from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_protected_ping_success_uses_v1_envelope_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    response = client.get("/v1/protected/ping", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert body["meta"]["spec_version"] == "v1"
    assert isinstance(body["data"]["tenant_id"], str)
    assert isinstance(body["data"]["user_id"], str)


def test_protected_ping_missing_token_uses_v1_envelope_contract() -> None:
    client = TestClient(app)
    response = client.get(
        "/v1/protected/ping",
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 401
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["data"] is None
    assert body["error"]["details"]["reason_code"] == "AUTH_TOKEN_MISSING"


def test_protected_ping_invalid_token_uses_v1_envelope_contract() -> None:
    client = TestClient(app)
    response = client.get(
        "/v1/protected/ping",
        headers={
            "Authorization": "Bearer invalid-token",
            "X-Correlation-ID": "test-correlation-id",
        },
    )

    assert response.status_code == 401
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["data"] is None
    assert body["error"]["details"]["reason_code"] == "AUTH_TOKEN_INVALID"
