from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_protected_ping_success_uses_v1_envelope_integration() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    response = client.get("/v1/protected/ping", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"
    assert body["error"] is None
    assert body["data"].get("message") == "Protected pong."


def test_protected_ping_missing_token_uses_unauthorized_integration() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["details"]["reason_code"] == "AUTH_TOKEN_MISSING"
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"


def test_protected_ping_invalid_token_uses_unauthorized_integration() -> None:
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
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["details"]["reason_code"] == "AUTH_TOKEN_INVALID"
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"
