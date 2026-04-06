from fastapi.testclient import TestClient

from app.main import app


def test_not_found_uses_standard_error_envelope() -> None:
    client = TestClient(app)
    response = client.get("/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()

    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], dict)
    assert isinstance(body["meta"]["timestamp"], str)
    assert isinstance(body["meta"]["correlation_id"], str)
