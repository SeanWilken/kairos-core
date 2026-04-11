from fastapi.testclient import TestClient

from app.main import app


HEADERS = {
    "X-Tenant-ID": "tenant0",
    "X-Org-ID": "org0",
    "X-Correlation-ID": "test-correlation-id",
}


def _create_session(client: TestClient) -> str:
    response = client.post(
        "/v1/bootstrap/sessions",
        headers=HEADERS,
        json={
            "runtime": {
                "tenant_name": "kairos-dev",
                "connections": [
                    {
                        "id": "1",
                        "mode": "api_provider",
                        "provider": "openai",
                        "endpoint": "https://api.openai.com/v1",
                        "model_ref": "gpt-4o-mini",
                        "priority": 1,
                    }
                ],
            },
            "deployment": {"infra_components": ["core_api", "postgres", "pgvector"]},
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["session_id"]


def test_system_status_contract() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.get("/v1/system/status", headers=HEADERS, params={"session_id": session_id})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert body["data"]["spec_version"] == "v0.2"
    assert body["data"]["session_id"] == session_id
    assert isinstance(body["data"]["checks"], list)
    assert body["data"]["summary"]["required_passed"] >= 1


def test_system_checks_run_contract() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/system/checks/run",
        headers=HEADERS,
        json={"session_id": session_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert body["data"]["session_id"] == session_id
    assert body["data"]["summary"]["required_failed"] == 0
    assert body["data"]["summary"]["required_pending"] == 0
