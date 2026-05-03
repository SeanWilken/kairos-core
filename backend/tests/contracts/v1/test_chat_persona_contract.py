from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_persona_chat_and_channel_policy_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+persona@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Ops Org", "slug": "ops-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "ops-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 3,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    persona_response = client.post(
        "/v1/studio/personas",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "Kairos Concierge",
            "slug": "kairos-concierge",
            "role": "guided-workflow-assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "data": {
                "prompt_blocks": {
                    "mission": "Help users make confident decisions.",
                    "instructions": "Clarify goals and provide next steps.",
                    "guardrails": ["Never fabricate"],
                }
            },
        },
    )
    assert persona_response.status_code == 200
    persona_id = persona_response.json()["data"]["persona"]["persona_id"]

    patch_policy = client.patch(
        f"/v1/studio/channels/{channel_id}/policy",
        headers=admin_headers,
        json={
            "default_persona_id": persona_id,
            "response_policy": "single_best",
            "responder_delay_seconds": 2,
        },
    )
    assert patch_policy.status_code == 200
    assert patch_policy.json()["data"]["default_persona_id"] == persona_id

    chat_response = client.post(
        f"/v1/studio/channels/{channel_id}/chat",
        headers=admin_headers,
        json={
            "content": "Help me plan onboarding for my operations team.",
            "persona_id": persona_id,
            "mode": "single_best",
        },
    )
    assert chat_response.status_code == 200
    body = chat_response.json()
    assert body["error"] is None
    assistant = body["data"]["assistant_message"]
    assert isinstance(assistant["content"], str)
    assert assistant["metadata"]["sender_kind"] == "assistant"
    assert assistant["metadata"]["mode"] == "single_best"
    assert assistant["metadata"]["persona_id"] == persona_id
    assert isinstance(assistant["metadata"]["provider"], str)
    assert isinstance(assistant["metadata"]["model"], str)


def test_persona_approval_policy_enforced_for_chat_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+approval@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Policy Org", "slug": "policy-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    settings_response = client.patch(
        "/v1/studio/settings",
        headers=admin_headers,
        json={"org_id": org_id, "settings": {"prompt_policy_mode": "approval_required"}},
    )
    assert settings_response.status_code == 200

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "approval-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 2,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    persona_response = client.post(
        "/v1/studio/personas",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "Compliance Assistant",
            "slug": "compliance-assistant",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "data": {"prompt_blocks": {"mission": "Stay compliant."}},
        },
    )
    assert persona_response.status_code == 200
    persona_id = persona_response.json()["data"]["persona"]["persona_id"]

    denied_chat = client.post(
        f"/v1/studio/channels/{channel_id}/chat",
        headers=admin_headers,
        json={"content": "Give me compliance guidance", "persona_id": persona_id},
    )
    assert denied_chat.status_code == 403
    assert denied_chat.json()["error"]["details"]["reason_code"] == "STUDIO_PERSONA_APPROVAL_REQUIRED"

    approve_response = client.post(
        f"/v1/studio/personas/{persona_id}/approval",
        headers=admin_headers,
        json={"approved": True},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["approval_status"] == "approved"

    allowed_chat = client.post(
        f"/v1/studio/channels/{channel_id}/chat",
        headers=admin_headers,
        json={"content": "Give me compliance guidance", "persona_id": persona_id},
    )
    assert allowed_chat.status_code == 200


def test_chat_fallback_requires_approval_then_executes_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+fallback@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Fallback Org", "slug": "fallback-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "fallback-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 1,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    persona_response = client.post(
        "/v1/studio/personas",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "Fallback Persona",
            "slug": "fallback-persona",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "fallback_policy": {
                "enabled": True,
                "approval_required": True,
                "provider_id": "google",
                "model_id": "gemini-2.5-flash",
            },
            "data": {"prompt_blocks": {"mission": "Use fallback only when approved."}},
        },
    )
    assert persona_response.status_code == 200
    persona_id = persona_response.json()["data"]["persona"]["persona_id"]

    class _Result:
        def __init__(self, content: str, provider: str, model: str) -> None:
            self.content = content
            self.provider = provider
            self.model = model
            self.usage = {"prompt_tokens": 12, "completion_tokens": 9, "total_tokens": 21}

    def _fake_completion(request):
        if getattr(request, "provider_id", None) == "google":
            return _Result("Fallback approved response", "google", "gemini-2.5-flash")
        raise RuntimeError("primary provider failed")

    with patch("app.api.v1.routes.chat.model_gateway.generate_text_sync", side_effect=_fake_completion):
        pending_chat = client.post(
            f"/v1/studio/channels/{channel_id}/chat",
            headers=admin_headers,
            json={"content": "Need fallback", "persona_id": persona_id},
        )
        assert pending_chat.status_code == 409
        assert pending_chat.json()["error"]["details"]["reason_code"] == "STUDIO_FALLBACK_APPROVAL_REQUIRED"
        request_id = pending_chat.json()["error"]["details"]["request_id"]

        list_response = client.get(
            "/v1/system/fallback-approvals",
            headers=admin_headers,
            params={"status": "pending"},
        )
        assert list_response.status_code == 200
        assert any(item["request_id"] == request_id for item in list_response.json()["data"]["items"])

        approve_response = client.post(
            f"/v1/system/fallback-approvals/{request_id}/decision",
            headers=admin_headers,
            json={"decision": "approve"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["data"]["status"] == "approved"

        allowed_chat = client.post(
            f"/v1/studio/channels/{channel_id}/chat",
            headers=admin_headers,
            json={"content": "Need fallback", "persona_id": persona_id},
        )
        assert allowed_chat.status_code == 200
        assistant = allowed_chat.json()["data"]["assistant_message"]
        assert assistant["metadata"]["provider"] == "google"
        assert assistant["metadata"]["fallback_approval_request_id"] == request_id


def test_persona_resume_export_provider_shapes_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+resume-shapes@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Resume Org", "slug": "resume-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    persona_response = client.post(
        "/v1/studio/personas",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "Resume Persona",
            "slug": "resume-persona",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "data": {
                "description": "Helps with planning and execution.",
                "skills": ["planning", "analysis"],
                "assigned_tools": ["chat_completion"],
                "selected_options": {
                    "personality_traits": ["direct", "clear"],
                    "communication_style": "precise",
                    "initiative_level": "high",
                },
                "guidelines": {
                    "do_list": ["state assumptions"],
                    "dont_list": ["guess private data"],
                    "guardrails": ["never fabricate citations"],
                },
            },
        },
    )
    assert persona_response.status_code == 200
    persona_id = persona_response.json()["data"]["persona"]["persona_id"]

    anthropic_export = client.get(
        f"/v1/studio/personas/{persona_id}/export-resume",
        headers=admin_headers,
        params={"provider_id": "anthropic", "model_id": "claude-sonnet-4-20250514"},
    )
    assert anthropic_export.status_code == 200
    anthropic_data = anthropic_export.json()["data"]["provider_export"]
    assert anthropic_data["provider_id"] == "anthropic"
    assert anthropic_data["format"] == "xml"
    assert "<persona_resume>" in anthropic_data["content"]

    openai_export = client.get(
        f"/v1/studio/personas/{persona_id}/export-resume",
        headers=admin_headers,
        params={"provider_id": "openai"},
    )
    assert openai_export.status_code == 200
    openai_data = openai_export.json()["data"]["provider_export"]
    assert openai_data["provider_id"] == "openai"
    assert openai_data["format"] == "text"
    assert "Persona Resume Context" in openai_data["content"]

    google_export = client.get(
        f"/v1/studio/personas/{persona_id}/export-resume",
        headers=admin_headers,
        params={"provider_id": "google"},
    )
    assert google_export.status_code == 200
    google_data = google_export.json()["data"]["provider_export"]
    assert google_data["provider_id"] == "google"
    assert google_data["format"] == "json"
    assert isinstance(google_data["content"], dict)
    assert google_data["content"]["instructions"]["format"] == "json"

    policy_create = client.post(
        "/v1/system/resume-adapter-policies",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "default",
            "config": {
                "provider_rules": [
                    {"provider_id": "openai", "model_pattern": "*", "format": "json"}
                ]
            },
        },
    )
    assert policy_create.status_code == 200
    policy_id = policy_create.json()["data"]["policy_id"]

    policy_activate = client.post(
        f"/v1/system/resume-adapter-policies/{policy_id}/activate",
        headers=admin_headers,
        json={"org_id": org_id},
    )
    assert policy_activate.status_code == 200

    overridden_export = client.get(
        f"/v1/studio/personas/{persona_id}/export-resume",
        headers=admin_headers,
        params={"provider_id": "openai", "model_id": "gpt-4o-mini"},
    )
    assert overridden_export.status_code == 200
    overridden_data = overridden_export.json()["data"]["provider_export"]
    assert overridden_data["format"] == "json"
    assert isinstance(overridden_data["content"], dict)
