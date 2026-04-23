from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


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


def test_ingest_job_requires_runtime_checks() -> None:
    client = TestClient(app)
    session_id = _create_session(client)
    auth_headers = register_and_login(client, scope_org_id="org0")

    response = client.post(
        "/v1/ingest/jobs",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "source_files": [{"path": "docs/intro.md", "checksum": "abc123"}],
            "chunking_profile": "recursive_512",
            "embedding_profile": "text-embedding-3-small",
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "PRECONDITION_FAILED"
    assert body["error"]["details"]["reason_code"] == "RUNTIME_CHECKS_NOT_PASSED"


def test_ingest_job_create_and_get_contract() -> None:
    client = TestClient(app)
    session_id = _create_session(client)
    auth_headers = register_and_login(client, scope_org_id="org0")

    checks_response = client.post(
        "/v1/system/checks/run",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    assert checks_response.status_code == 200

    create_response = client.post(
        "/v1/ingest/jobs",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "source_files": [{"path": "docs/intro.md", "checksum": "abc123"}],
            "chunking_profile": "recursive_512",
            "embedding_profile": "text-embedding-3-small",
            "namespace": "tenant_default",
        },
    )

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert set(create_body.keys()) == {"meta", "data", "error"}
    assert create_body["error"] is None
    assert create_body["data"]["spec_version"] == "v0.2"
    assert create_body["data"]["status"] == "completed"
    assert create_body["data"]["session_id"] == session_id

    job_id = create_body["data"]["job_id"]
    get_response = client.get(f"/v1/ingest/jobs/{job_id}", headers=auth_headers)
    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body["error"] is None
    assert get_body["data"]["job_id"] == job_id
