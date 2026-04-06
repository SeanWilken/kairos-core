from fastapi.testclient import TestClient

from app.main import app


def test_v1_not_found_uses_envelope_contract() -> None:
    client = TestClient(app)
    response = client.get("/v1/missing-route")

    assert response.status_code == 404
    body = response.json()

    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], dict)
