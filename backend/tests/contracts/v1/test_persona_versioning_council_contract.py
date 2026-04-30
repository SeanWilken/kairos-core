from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_persona_versioning_and_rollback_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="version.owner@kairos.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Version Org", "slug": "version-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    persona_create = client.post(
        "/v1/studio/personas",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Versioned Persona",
            "slug": "versioned-persona",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "system_prompt": "Initial prompt",
            "data": {"traits": ["concise"]},
        },
    )
    assert persona_create.status_code == 200
    persona = persona_create.json()["data"]["persona"]
    persona_id = persona["persona_id"]
    assert persona_create.json()["data"]["version"]["version_string"] == "1.0.0"

    persona_update = client.patch(
        f"/v1/studio/personas/{persona_id}",
        headers=headers,
        json={
            "system_prompt": "Major updated prompt",
            "version_bump": "major",
            "change_summary": "Policy migration",
        },
    )
    assert persona_update.status_code == 200
    assert persona_update.json()["data"]["version"]["version_string"] == "2.0.0"

    versions = client.get(f"/v1/studio/personas/{persona_id}/versions", headers=headers)
    assert versions.status_code == 200
    items = versions.json()["data"]["items"]
    assert len(items) == 2
    rollback_target = items[-1]["version_id"]

    rollback = client.post(
        f"/v1/studio/personas/{persona_id}/rollback/{rollback_target}",
        headers=headers,
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["persona"]["system_prompt"] == "Initial prompt"
    assert rollback.json()["data"]["version"]["version_string"] == "2.0.1"


def test_council_config_and_room_persona_assignment_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="council.owner@kairos.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Council Org", "slug": "council-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    channel = client.post(
        "/v1/studio/channels",
        headers=headers,
        json={
            "org_id": org_id,
            "channel_type": "org",
            "name": "council-room",
            "retention_days": 30,
        },
    )
    assert channel.status_code == 200
    channel_id = channel.json()["data"]["channel_id"]

    persona = client.post(
        "/v1/studio/personas",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Council Head",
            "slug": "council-head",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "data": {},
        },
    )
    assert persona.status_code == 200
    persona_id = persona.json()["data"]["persona"]["persona_id"]

    config = client.patch(
        f"/v1/studio/channels/{channel_id}/council-config",
        headers=headers,
        json={
            "council_head_persona_id": persona_id,
            "council_mode": "summarized",
            "delay_before_orchestration_ms": 12000,
            "show_reasoning_metadata": True,
            "allow_parallel_responses": False,
        },
    )
    assert config.status_code == 200
    assert config.json()["data"]["council_head_persona_id"] == persona_id

    room_personas = client.put(
        f"/v1/studio/channels/{channel_id}/personas",
        headers=headers,
        json={"personas": [{"persona_id": persona_id, "role_in_room": "head", "sort_order": 1}]},
    )
    assert room_personas.status_code == 200
    assert len(room_personas.json()["data"]["items"]) == 1

    read_back = client.get(f"/v1/studio/channels/{channel_id}/council-config", headers=headers)
    assert read_back.status_code == 200
    assert read_back.json()["data"]["config"]["council_head_persona_id"] == persona_id
    assert len(read_back.json()["data"]["personas"]) == 1


def test_user_persona_context_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="context.owner@kairos.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Context Org", "slug": "context-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    persona = client.post(
        "/v1/studio/personas",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Coach Persona",
            "slug": "coach-persona",
            "role": "assistant",
            "scope": "organization",
            "enabled": True,
            "model_profile": "reasoning-optimized",
            "data": {},
        },
    )
    assert persona.status_code == 200
    persona_id = persona.json()["data"]["persona"]["persona_id"]

    me = client.get("/v1/auth/me", headers=headers)
    assert me.status_code == 200
    user_id = me.json()["data"]["user"]["user_id"]

    upsert = client.put(
        f"/v1/studio/users/{user_id}/persona-contexts/{persona_id}",
        headers=headers,
        json={
            "user_strengths": ["architecture"],
            "user_weaknesses": ["qa automation"],
            "autonomy_level": "moderate",
            "communication_preference": "balanced",
            "detail_level": "standard",
            "check_in_frequency": "as_needed",
            "context": {"timezone": "UTC"},
        },
    )
    assert upsert.status_code == 200
    assert upsert.json()["data"]["user_strengths"] == ["architecture"]

    read_one = client.get(
        f"/v1/studio/users/{user_id}/persona-contexts/{persona_id}",
        headers=headers,
    )
    assert read_one.status_code == 200
    assert read_one.json()["data"]["context"]["timezone"] == "UTC"

    read_many = client.get(f"/v1/studio/users/{user_id}/persona-contexts", headers=headers)
    assert read_many.status_code == 200
    assert len(read_many.json()["data"]["items"]) == 1
