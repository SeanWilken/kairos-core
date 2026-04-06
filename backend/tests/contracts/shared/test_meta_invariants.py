from fastapi.testclient import TestClient

from app.main import app


def test_meta_is_present_on_success_and_error() -> None:
    client = TestClient(app)

    success = client.get("/v1/health").json()
    missing = client.get("/v1/route-that-does-not-exist").json()

    assert "meta" in success
    assert "meta" in missing

    for body in [success, missing]:
        assert isinstance(body["meta"]["service"], str)
        assert isinstance(body["meta"]["version"], str)
        assert isinstance(body["meta"]["environment"], str)
        assert isinstance(body["meta"]["timestamp"], str)
        assert isinstance(body["meta"]["correlation_id"], str)
