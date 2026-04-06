from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_envelope_and_correlation_header() -> None:
    client = TestClient(app)
    response = client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()

    assert body["data"] == {"status": "ok"}
    assert body["error"] is None
    assert isinstance(body["meta"]["correlation_id"], str)
    assert "X-Correlation-ID" in response.headers
