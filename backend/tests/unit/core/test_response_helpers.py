from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient

from app.core.response import error_response, ok_response


def test_ok_response_sets_data_and_null_error() -> None:
    app = FastAPI()

    @app.middleware("http")
    async def add_correlation_id(request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "cid-ok"
        return await call_next(request)

    @app.get("/probe")
    def probe(request: Request) -> dict:
        return ok_response(request, {"status": "ok"})

    response = TestClient(app).get("/probe")
    body = response.json()

    assert response.status_code == 200
    assert body["data"] == {"status": "ok"}
    assert body["error"] is None
    assert body["meta"]["correlation_id"] == "cid-ok"


def test_error_response_sets_error_and_null_data() -> None:
    app = FastAPI()

    @app.middleware("http")
    async def add_correlation_id(request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "cid-error"
        return await call_next(request)

    @app.get("/probe")
    def probe(request: Request) -> dict:
        return error_response(request, "NOT_FOUND", "Missing", {"target": "x"})

    response = TestClient(app).get("/probe")
    body = response.json()

    assert response.status_code == 200
    assert body["data"] is None
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["details"] == {"target": "x"}
