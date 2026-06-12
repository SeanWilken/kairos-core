from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_persona_chat_and_channel_policy_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+persona@myai.dev")

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
            "name": "MyAI Concierge",
            "slug": "myai-concierge",
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
    chat_options = body["data"].get("chat_options", {})
    assert "markdown" in chat_options.get("response_types", [])
    assert isinstance(chat_options.get("participant_options", []), list)


def test_chat_response_type_markdown_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+markdown@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Markdown Org", "slug": "markdown-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "markdown-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 1,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    chat_response = client.post(
        f"/v1/studio/channels/{channel_id}/chat",
        headers=admin_headers,
        json={
            "content": "Explain dependency injection patterns.",
            "mode": "single_best",
            "response_type": "markdown",
        },
    )
    assert chat_response.status_code == 200
    data = chat_response.json()["data"]
    assert "chat_options" in data
    assistant = data["assistant_message"]
    assert assistant["metadata"]["response_type"] == "markdown"
    structured = assistant["metadata"]["structured_content"]
    assert structured["primary_type"] == "markdown"
    assert structured["render_hint"] == "markdown"
    assert structured["blocks"][0]["type"] == "markdown"
    assert structured["blocks"][0]["block_id"] == "block:0"
    assert structured["blocks"][0]["capabilities"]["editable"] is True
    assert structured["blocks"][0]["capabilities"]["replyable"] is True


def test_chat_mixed_text_and_markdown_blocks_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+mixed@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Mixed Org", "slug": "mixed-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "mixed-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 1,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    class _Result:
        def __init__(self, content: str, provider: str, model: str) -> None:
            self.content = content
            self.provider = provider
            self.model = model
            self.usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}

    def _fake_completion(_request):
        return _Result(
            "Some text paragraph here explaining or reviewing things.\n\n## Markdown section\n- item one\n- item two\n\nMore text response about something.",
            "openai",
            "gpt-4o-mini",
        )

    with patch("app.api.v1.routes.chat.model_gateway.generate_text_sync", side_effect=_fake_completion):
        response = client.post(
            f"/v1/studio/channels/{channel_id}/chat",
            headers=admin_headers,
            json={"content": "Respond with mixed formatting.", "mode": "single_best", "response_type": "markdown"},
        )

    assert response.status_code == 200
    assistant = response.json()["data"]["assistant_message"]
    structured = assistant["metadata"]["structured_content"]
    assert structured["primary_type"] == "mixed"
    assert structured["render_hint"] == "structured_blocks"
    assert [block["type"] for block in structured["blocks"]] == ["text", "markdown", "text"]
    assert [block["block_id"] for block in structured["blocks"]] == ["block:0", "block:1", "block:2"]
    assert structured["blocks"][0]["capabilities"]["editable"] is False
    assert structured["blocks"][1]["capabilities"]["editable"] is True


def test_chat_strict_validation_rejects_unknown_fields_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+strict@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Strict Org", "slug": "strict-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "strict-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 1,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    response = client.post(
        f"/v1/studio/channels/{channel_id}/chat",
        headers=admin_headers,
        json={
            "content": "hello",
            "mode": "single_best",
            "strict_validation": True,
            "unknown_field": "boom",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason_code"] == "CHAT_PAYLOAD_VALIDATION_FAILED"


def test_restricted_admin_persona_hidden_for_member_contract() -> None:
    client = TestClient(app)
    owner_headers = register_and_login(client, email="owner+restricted@myai.dev", is_global_admin=False)

    org_response = client.post(
        "/v1/studio/organizations",
        headers=owner_headers,
        json={"name": "Restricted Org", "slug": "restricted-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    restricted = client.post(
        "/v1/studio/personas",
        headers=owner_headers,
        json={
            "org_id": org_id,
            "name": "Admin Planner",
            "slug": "admin-planner",
            "role": "planner",
            "scope": "organization",
            "enabled": True,
            "data": {
                "access_policy": {"visibility": "admin_only"},
                "prompt_blocks": {"mission": "Internal planning"},
            },
        },
    )
    assert restricted.status_code == 200
    restricted_id = restricted.json()["data"]["persona"]["persona_id"]

    public = client.post(
        "/v1/studio/personas",
        headers=owner_headers,
        json={
            "org_id": org_id,
            "name": "Public Helper",
            "slug": "public-helper",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "data": {"prompt_blocks": {"mission": "General help"}},
        },
    )
    assert public.status_code == 200

    member_headers = register_and_login(
        client,
        email="member+restricted@myai.dev",
        is_global_admin=False,
        org_id=org_id,
    )

    list_response = client.get("/v1/studio/personas", headers=member_headers, params={"org_id": org_id})
    assert list_response.status_code == 200
    persona_ids = {item["persona_id"] for item in list_response.json()["data"]["items"]}
    assert restricted_id not in persona_ids

    restricted_get = client.get(f"/v1/studio/personas/{restricted_id}", headers=member_headers)
    assert restricted_get.status_code == 403
    assert restricted_get.json()["error"]["details"]["reason_code"] == "STUDIO_PERSONA_ACCESS_FORBIDDEN"


def test_list_personas_with_unknown_org_returns_not_found() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+unknown-org@myai.dev")

    response = client.get(
        "/v1/studio/personas",
        headers=admin_headers,
        params={"org_id": "Development"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["details"]["reason_code"] == "STUDIO_ORG_NOT_FOUND"


def test_persona_approval_policy_enforced_for_chat_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+approval@myai.dev")

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
    admin_headers = register_and_login(client, email="admin+fallback@myai.dev")

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


def test_chat_image_command_creates_attachment_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+image@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Image Org", "slug": "image-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "image-chat",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 1,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    chat_response = client.post(
        f"/v1/studio/channels/{channel_id}/chat",
        headers=admin_headers,
        json={"content": "/image Generate a clean dashboard hero", "mode": "single_best"},
    )
    assert chat_response.status_code == 200
    assistant = chat_response.json()["data"]["assistant_message"]
    attachments = assistant["metadata"].get("attachments", [])
    assert isinstance(attachments, list)
    assert attachments and attachments[0]["type"] == "image"
    assert assistant["metadata"]["tool_call"]["tool_id"] == "nano_banana"


def test_persona_resume_export_provider_shapes_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+resume-shapes@myai.dev")

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
