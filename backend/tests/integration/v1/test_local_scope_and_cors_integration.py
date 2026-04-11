from fastapi.testclient import TestClient

from app.main import app


def test_bootstrap_session_allows_local_scope_fallback_for_non_protected_routes() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/bootstrap/sessions",
        headers={"X-Correlation-ID": "test-correlation-id"},
        json={
            "runtime": {"tenant_name": "local-bootstrap"},
            "deployment": {"infra_components": ["core_api"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["tenant_id"] == "tenant-local"
    assert body["data"]["org_id"] == "org-local"


def test_protected_ping_still_requires_scope_headers() -> None:
    client = TestClient(app)

    response = client.get(
        "/v1/protected/ping",
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "ACCESS_DENIED"


def test_bootstrap_route_supports_local_cors_preflight() -> None:
    client = TestClient(app)

    response = client.options(
        "/v1/bootstrap/sessions",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods
