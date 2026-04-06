from fastapi.testclient import TestClient

from app.main import app


def test_v1_health_success_uses_envelope_contract() -> None:
    client = TestClient(app)
    response = client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert body["data"] == {"status": "ok"}
