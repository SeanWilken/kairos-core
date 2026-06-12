from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_studio_membership_create_and_patch_role_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Core Team", "slug": "core-team", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    user = client.post(
        "/v1/studio/users",
        headers=headers,
        json={
            "email": "global.owner@myai.dev",
            "first_name": "Global",
            "last_name": "Owner",
            "is_global_admin": True,
        },
    )
    assert user.status_code == 200
    user_id = user.json()["data"]["user_id"]

    membership = client.post(
        "/v1/studio/memberships",
        headers=headers,
        json={
            "org_id": org_id,
            "user_id": user_id,
            "role": "member",
        },
    )
    assert membership.status_code == 200
    membership_body = membership.json()
    assert membership_body["error"] is None
    assert membership_body["data"]["role"] == "member"

    membership_id = membership_body["data"]["membership_id"]
    patched = client.patch(
        f"/v1/studio/memberships/{membership_id}",
        headers=headers,
        json={"role": "owner"},
    )

    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["error"] is None
    assert patched_body["data"]["role"] == "owner"


def test_studio_membership_patch_empty_payload_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    response = client.patch(
        "/v1/studio/memberships/missing",
        headers=headers,
        json={},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_MEMBERSHIP_PATCH_EMPTY"
