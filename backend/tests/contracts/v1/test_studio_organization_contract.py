from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_studio_organization_create_list_get_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)

    create = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "MyAI Team", "slug": "myai-team", "mode": "team"},
    )
    assert create.status_code == 200
    create_body = create.json()
    assert create_body["error"] is None
    org_id = create_body["data"]["org_id"]

    listed = client.get("/v1/studio/organizations", headers=headers)
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body["data"]["items"], list)
    assert any(item["org_id"] == org_id for item in listed_body["data"]["items"])

    fetched = client.get(f"/v1/studio/organizations/{org_id}", headers=headers)
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["error"] is None
    assert fetched_body["data"]["slug"] == "myai-team"


def test_studio_organization_not_found_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client)
    response = client.get("/v1/studio/organizations/missing-org", headers=headers)

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_NOT_FOUND"
