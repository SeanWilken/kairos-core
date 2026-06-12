from fastapi.testclient import TestClient

from app.main import app


HEADERS = {
    "X-Tenant-ID": "tenant0",
    "X-Org-ID": "org0",
    "X-Correlation-ID": "test-correlation-id",
}


def test_bootstrap_session_create_and_get_contract() -> None:
    client = TestClient(app)

    create_response = client.post(
        "/v1/bootstrap/sessions",
        headers=HEADERS,
        json={
            "runtime": {
                "tenant_name": "myai-dev",
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

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert set(create_body.keys()) == {"meta", "data", "error"}
    assert create_body["error"] is None
    assert create_body["data"]["spec_version"] == "v0.2"
    assert create_body["data"]["tenant_id"] == "tenant0"
    assert create_body["data"]["org_id"] == "org0"

    session_id = create_body["data"]["session_id"]
    get_response = client.get(f"/v1/bootstrap/sessions/{session_id}", headers=HEADERS)

    assert get_response.status_code == 200
    get_body = get_response.json()
    assert set(get_body.keys()) == {"meta", "data", "error"}
    assert get_body["error"] is None
    assert get_body["data"]["session_id"] == session_id
    assert get_body["meta"]["spec_version"] == "v1"


def test_bootstrap_session_list_and_latest_contract() -> None:
    client = TestClient(app)

    first = client.post(
        "/v1/bootstrap/sessions",
        headers=HEADERS,
        json={
            "runtime": {"tenant_name": "myai-a"},
            "deployment": {"infra_components": ["core_api"]},
        },
    )
    assert first.status_code == 200
    first_id = first.json()["data"]["session_id"]

    second = client.post(
        "/v1/bootstrap/sessions",
        headers=HEADERS,
        json={
            "runtime": {"tenant_name": "myai-b"},
            "deployment": {"infra_components": ["core_api"]},
        },
    )
    assert second.status_code == 200
    second_id = second.json()["data"]["session_id"]

    list_response = client.get("/v1/bootstrap/sessions", headers=HEADERS)
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert isinstance(list_body["data"], list)
    assert any(row["session_id"] == first_id for row in list_body["data"])
    assert any(row["session_id"] == second_id for row in list_body["data"])

    latest_response = client.get("/v1/bootstrap/sessions?latest=true", headers=HEADERS)
    assert latest_response.status_code == 200
    latest_body = latest_response.json()
    assert latest_body["error"] is None
    assert latest_body["data"]["session_id"] == second_id
