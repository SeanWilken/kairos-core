from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_channel_message_and_task_visibility_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+chat@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Devices Org", "slug": "devices-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    team_response = client.post(
        "/v1/studio/teams",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "Phone Team",
            "slug": "phone-team",
            "access_mode": "internal",
        },
    )
    assert team_response.status_code == 200
    team_id = team_response.json()["data"]["team_id"]

    member_headers = register_and_login(
        client,
        email="member+chat@kairos.dev",
        is_global_admin=False,
        org_id=org_id,
        scope_org_id=org_id,
    )
    member_user_id = client.get("/v1/auth/me", headers=member_headers).json()["data"]["user"]["user_id"]

    add_team_member = client.post(
        f"/v1/studio/teams/{team_id}/memberships",
        headers=admin_headers,
        json={"user_id": member_user_id, "role": "member", "status": "active"},
    )
    assert add_team_member.status_code == 200

    create_channel = client.post(
        "/v1/studio/channels",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "channel_type": "team",
            "name": "phone-team-room",
            "team_id": team_id,
            "retention_days": 45,
            "participant_user_ids": [member_user_id],
        },
    )
    assert create_channel.status_code == 200
    channel_body = create_channel.json()["data"]
    channel_id = channel_body["channel_id"]
    assert channel_body["retention_days"] == 45

    send_admin_message = client.post(
        f"/v1/studio/channels/{channel_id}/messages",
        headers=admin_headers,
        json={"content": "Kickoff update"},
    )
    assert send_admin_message.status_code == 200

    send_member_message = client.post(
        f"/v1/studio/channels/{channel_id}/messages",
        headers=member_headers,
        json={"content": "Received and working"},
    )
    assert send_member_message.status_code == 200

    list_messages = client.get(
        f"/v1/studio/channels/{channel_id}/messages",
        headers=member_headers,
    )
    assert list_messages.status_code == 200
    messages = list_messages.json()["data"]["items"]
    assert len(messages) == 2

    private_task = client.post(
        "/v1/studio/tasks",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "title": "Private leadership task",
            "visibility": "private_owner",
        },
    )
    assert private_task.status_code == 200
    private_task_id = private_task.json()["data"]["task_id"]

    team_task = client.post(
        "/v1/studio/tasks",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "team_id": team_id,
            "title": "Phone release checklist",
            "visibility": "team_public",
        },
    )
    assert team_task.status_code == 200
    team_task_id = team_task.json()["data"]["task_id"]

    assign_task = client.post(
        f"/v1/studio/tasks/{team_task_id}/assignments",
        headers=admin_headers,
        json={"assignee_user_id": member_user_id},
    )
    assert assign_task.status_code == 200

    member_tasks = client.get(
        f"/v1/studio/tasks?org_id={org_id}",
        headers=member_headers,
    )
    assert member_tasks.status_code == 200
    member_task_ids = {row["task_id"] for row in member_tasks.json()["data"]["items"]}
    assert team_task_id in member_task_ids
    assert private_task_id not in member_task_ids

    private_read_attempt = client.get(
        f"/v1/studio/tasks/{private_task_id}",
        headers=member_headers,
    )
    assert private_read_attempt.status_code == 403
