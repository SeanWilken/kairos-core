from fastapi.testclient import TestClient

from app.main import app


def test_v1_health_contract_meta_fields() -> None:
    client = TestClient(app)
    response = client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    meta = body["meta"]

    assert isinstance(meta["service"], str)
    assert isinstance(meta["version"], str)
    assert isinstance(meta["environment"], str)
    assert isinstance(meta["timestamp"], str)
    assert isinstance(meta["correlation_id"], str)
    assert meta["correlation_id"]
