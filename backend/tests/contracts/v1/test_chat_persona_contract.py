from fastapi.testclient import TestClient

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
    persona_id = persona_response.json()["data"]["persona_id"]

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
