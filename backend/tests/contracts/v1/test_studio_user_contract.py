from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def _create_org(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "MyAI Labs", "slug": "myai-labs", "mode": "team"},
    )
    assert response.status_code == 200
    return response.json()["data"]["org_id"]


def test_studio_user_create_and_get_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)
    org_id = _create_org(client, headers)

    create_response = client.post(
        "/v1/studio/users",
        headers=headers,
        json={
            "email": "owner@myai.dev",
            "first_name": "Global",
            "last_name": "Admin",
            "org_id": org_id,
            "is_global_admin": True,
            "role": "owner",
        },
    )

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert set(create_body.keys()) == {"meta", "data", "error"}
    assert create_body["error"] is None
    assert create_body["data"]["email"] == "owner@myai.dev"
    assert create_body["data"]["membership"]["org_id"] == org_id

    user_id = create_body["data"]["user_id"]
    get_response = client.get(f"/v1/studio/users/{user_id}", headers=headers)

    assert get_response.status_code == 200
    get_body = get_response.json()
    assert get_body["error"] is None
    assert get_body["data"]["user_id"] == user_id
    assert get_body["meta"]["spec_version"] == "v1"


def test_studio_user_list_and_duplicate_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)
    org_id = _create_org(client, headers)

    first = client.post(
        "/v1/studio/users",
        headers=headers,
        json={
            "email": "operator@myai.dev",
            "first_name": "Ops",
            "last_name": "One",
            "org_id": org_id,
        },
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/v1/studio/users",
        headers=headers,
        json={
            "email": "operator@myai.dev",
            "first_name": "Ops",
            "last_name": "Two",
            "org_id": org_id,
        },
    )
    assert duplicate.status_code == 409
    duplicate_body = duplicate.json()
    assert duplicate_body["error"]["details"]["reason_code"] == "STUDIO_USER_EMAIL_EXISTS"

    listed = client.get(f"/v1/studio/users?org_id={org_id}", headers=headers)
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body["data"]["items"], list)
    assert any(item["email"] == "operator@myai.dev" for item in listed_body["data"]["items"])


def test_global_admin_can_be_created_without_org_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    response = client.post(
        "/v1/studio/users",
        headers=headers,
        json={
            "email": "global@myai.dev",
            "first_name": "Global",
            "last_name": "Owner",
            "is_global_admin": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["is_global_admin"] is True
    assert body["data"]["membership"] is None


def test_non_global_user_without_org_is_rejected_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    response = client.post(
        "/v1/studio/users",
        headers=headers,
        json={
            "email": "member@myai.dev",
            "first_name": "Local",
            "last_name": "Member",
            "is_global_admin": False,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_REQUIRED_FOR_USER"
