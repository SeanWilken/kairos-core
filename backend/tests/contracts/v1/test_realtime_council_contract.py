from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_realtime_council_summarized_orchestration_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="realtime.council@kairos.dev")
    token = headers["Authorization"].split(" ", 1)[1]

    org_response = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Realtime Org", "slug": "realtime-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    channel_response = client.post(
        "/v1/studio/channels",
        headers=headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "realtime-council-room",
            "retention_days": 30,
            "response_policy": "single_best",
            "auto_respond": True,
            "responder_delay_seconds": 1,
        },
    )
    assert channel_response.status_code == 200
    channel_id = channel_response.json()["data"]["channel_id"]

    p1 = client.post(
        "/v1/studio/personas",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Council Head",
            "slug": "council-head-realtime",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "data": {},
        },
    )
    assert p1.status_code == 200
    p1_id = p1.json()["data"]["persona"]["persona_id"]

    p2 = client.post(
        "/v1/studio/personas",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Council Member",
            "slug": "council-member-realtime",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "data": {},
        },
    )
    assert p2.status_code == 200
    p2_id = p2.json()["data"]["persona"]["persona_id"]

    config_response = client.patch(
        f"/v1/studio/channels/{channel_id}/council-config",
        headers=headers,
        json={
            "council_head_persona_id": p1_id,
            "council_mode": "summarized",
            "delay_before_orchestration_ms": 0,
            "show_reasoning_metadata": True,
            "allow_parallel_responses": True,
        },
    )
    assert config_response.status_code == 200

    room_personas_response = client.put(
        f"/v1/studio/channels/{channel_id}/personas",
        headers=headers,
        json={
            "personas": [
                {"persona_id": p1_id, "role_in_room": "head", "sort_order": 1},
                {"persona_id": p2_id, "role_in_room": "member", "sort_order": 2},
            ]
        },
    )
    assert room_personas_response.status_code == 200

    with client.websocket_connect(f"/v1/realtime/ws?token={token}") as websocket:
        connected = websocket.receive_json()
        assert connected["event"] == "system.connected"

        websocket.send_json(
            {
                "action": "chat.send",
                "channel_id": channel_id,
                "content": "Please synthesize next steps for the release.",
                "mode": "council",
            }
        )

        events: set[str] = set()
        for _ in range(10):
            event = websocket.receive_json()
            event_name = event.get("event")
            if isinstance(event_name, str):
                events.add(event_name)
            if {
                "chat.message.user.created",
                "council.delayed_start",
                "council.response",
            }.issubset(events):
                break

        assert "chat.message.user.created" in events
        assert "council.delayed_start" in events
        assert "council.response" in events
