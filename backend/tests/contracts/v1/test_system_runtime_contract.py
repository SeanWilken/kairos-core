from fastapi.testclient import TestClient

from app.main import app
from app.core.fallback_store import fallback_store
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
    auth_headers = register_and_login(client, scope_org_id="org0")

    response = client.post(
        "/v1/system/checks/run",
        headers=auth_headers,
        json={"session_id": session_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert body["data"]["session_id"] == session_id
    assert body["data"]["summary"]["required_failed"] == 0
    assert body["data"]["summary"]["required_pending"] == 0


def test_system_ai_provider_catalog_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    response = client.get("/v1/system/ai/providers", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"meta", "data", "error"}
    assert body["error"] is None
    assert isinstance(body["data"]["providers"], list)
    assert isinstance(body["data"]["routing"], dict)


def test_system_ai_provider_models_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    response = client.get(
        "/v1/system/ai/providers/google/models",
        headers=auth_headers,
        params={"capability": "image_generation"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["provider_id"] == "google"
    assert body["data"]["capability"] == "image_generation"
    assert isinstance(body["data"]["models"], list)


def test_system_audit_events_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    response = client.get("/v1/system/audit/events", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert isinstance(body["data"]["items"], list)


def test_system_fallback_approval_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")
    request = fallback_store.create_request(
        tenant_id="tenant0",
        org_id="org0",
        room_id="room-contract",
        orchestration_run_id="",
        persona_id="persona-contract",
        source_provider_id="openai",
        source_model_id="gpt-4o-mini",
        fallback_provider_id="google",
        fallback_model_id="gemini-2.5-flash",
        trigger_reason="contract_test",
        created_by_user_id="u-contract",
        metadata={"source": "test"},
    )

    list_response = client.get(
        "/v1/system/fallback-approvals",
        headers=auth_headers,
        params={"status": "pending"},
    )
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["error"] is None
    assert isinstance(list_body["data"]["items"], list)

    decide_response = client.post(
        f"/v1/system/fallback-approvals/{request['request_id']}/decision",
        headers=auth_headers,
        json={"decision": "approve"},
    )
    assert decide_response.status_code == 200
    decide_body = decide_response.json()
    assert decide_body["error"] is None
    assert decide_body["data"]["request_id"] == request["request_id"]
    assert decide_body["data"]["status"] == "approved"


def test_resume_adapter_policy_management_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    create_response = client.post(
        "/v1/system/resume-adapter-policies",
        headers=auth_headers,
        json={
            "org_id": "org0",
            "name": "default",
            "config": {
                "provider_rules": [
                    {"provider_id": "openai", "model_pattern": "*", "format": "json"}
                ]
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["name"] == "default"

    activate_response = client.post(
        f"/v1/system/resume-adapter-policies/{created['policy_id']}/activate",
        headers=auth_headers,
        json={"org_id": "org0"},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["status"] == "active"

    list_response = client.get(
        "/v1/system/resume-adapter-policies",
        headers=auth_headers,
        params={"org_id": "org0"},
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert any(item["policy_id"] == created["policy_id"] for item in items)

    rollback_response = client.post(
        f"/v1/system/resume-adapter-policies/{created['policy_id']}/rollback",
        headers=auth_headers,
        json={"org_id": "org0"},
    )
    assert rollback_response.status_code == 200
    rolled = rollback_response.json()["data"]
    assert rolled["status"] == "active"
    assert rolled["rolled_back_from_policy_id"] == created["policy_id"]


def test_prompt_template_version_activation_and_resolution_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    version_response = client.post(
        "/v1/system/prompt-templates/versions",
        headers=auth_headers,
        json={
            "provider_id": "openai",
            "template_kind": "system_prompt",
            "name": "default",
            "content": "You are {{persona.name}}. {{persona.base_prompt}}",
        },
    )
    assert version_response.status_code == 200
    version = version_response.json()["data"]

    activate_response = client.post(
        "/v1/system/prompt-templates/activations",
        headers=auth_headers,
        json={
            "scope_level": "org",
            "scope_id": "org0",
            "provider_id": "openai",
            "template_kind": "system_prompt",
            "template_version_id": version["template_version_id"],
            "reason": "contract activation",
        },
    )
    assert activate_response.status_code == 200
    activation = activate_response.json()["data"]

    resolve_response = client.get(
        "/v1/system/prompt-templates/resolve",
        headers=auth_headers,
        params={"provider_id": "openai", "template_kind": "system_prompt", "org_id": "org0"},
    )
    assert resolve_response.status_code == 200
    resolved = resolve_response.json()["data"]
    assert resolved["scope_level"] == "org"
    assert resolved["version"]["template_version_id"] == version["template_version_id"]

    rollback_response = client.post(
        f"/v1/system/prompt-templates/activations/{activation['activation_id']}/rollback",
        headers=auth_headers,
    )
    assert rollback_response.status_code == 200


def test_model_gateway_policy_management_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    create_response = client.post(
        "/v1/system/model-gateway-policies",
        headers=auth_headers,
        json={
            "org_id": "org0",
            "name": "default",
            "config": {
                "provider_rules": [
                    {
                        "provider_id": "openai",
                        "model_pattern": "gpt-*",
                        "timeout_seconds": 22,
                        "retries": 2,
                    }
                ]
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]

    activate_response = client.post(
        f"/v1/system/model-gateway-policies/{created['policy_id']}/activate",
        headers=auth_headers,
        json={"org_id": "org0"},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["status"] == "active"

    list_response = client.get(
        "/v1/system/model-gateway-policies",
        headers=auth_headers,
        params={"org_id": "org0"},
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert any(item["policy_id"] == created["policy_id"] for item in items)

    rollback_response = client.post(
        f"/v1/system/model-gateway-policies/{created['policy_id']}/rollback",
        headers=auth_headers,
        json={"org_id": "org0"},
    )
    assert rollback_response.status_code == 200
