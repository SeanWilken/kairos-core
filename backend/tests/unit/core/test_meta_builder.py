from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.response import build_meta


def test_build_meta_uses_request_state_correlation_id() -> None:
    app = FastAPI()

    @app.get("/meta")
    def meta_probe() -> dict:
        return {}

    @app.middleware("http")
    async def add_correlation_id(request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "cid-test"
        return await call_next(request)

    @app.get("/run")
    def run(request: Request) -> dict:
        return build_meta(request).model_dump()

    client = TestClient(app)
    response = client.get("/run")

    assert response.status_code == 200
    body = response.json()
    assert body["correlation_id"] == "cid-test"
