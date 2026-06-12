from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_division_team_and_team_membership_contract() -> None:
    client = TestClient(app)
    admin_headers = register_and_login(client, email="admin+team@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=admin_headers,
        json={"name": "Product Org", "slug": "product-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    division_response = client.post(
        "/v1/studio/divisions",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "name": "Product Development",
            "slug": "product-development",
            "description": "Main product division",
        },
    )
    assert division_response.status_code == 200
    division_id = division_response.json()["data"]["division_id"]

    team_response = client.post(
        "/v1/studio/teams",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "division_id": division_id,
            "name": "Laptop Team",
            "slug": "laptop-team",
            "access_mode": "internal",
        },
    )
    assert team_response.status_code == 200
    team_id = team_response.json()["data"]["team_id"]

    child_team_response = client.post(
        "/v1/studio/teams",
        headers=admin_headers,
        json={
            "org_id": org_id,
            "parent_team_id": team_id,
            "name": "Laptop Hardware",
            "slug": "laptop-hardware",
            "access_mode": "internal",
        },
    )
    assert child_team_response.status_code == 200

    member_headers = register_and_login(
        client,
        email="member+team@myai.dev",
        is_global_admin=False,
        org_id=org_id,
        scope_org_id=org_id,
    )
    member_me = client.get("/v1/auth/me", headers=member_headers)
    assert member_me.status_code == 200
    member_user_id = member_me.json()["data"]["user"]["user_id"]

    create_membership = client.post(
        f"/v1/studio/teams/{team_id}/memberships",
        headers=admin_headers,
        json={"user_id": member_user_id, "role": "member", "status": "active"},
    )
    assert create_membership.status_code == 200
    membership_id = create_membership.json()["data"]["team_membership_id"]

    list_memberships = client.get(
        f"/v1/studio/teams/{team_id}/memberships",
        headers=admin_headers,
    )
    assert list_memberships.status_code == 200
    items = list_memberships.json()["data"]["items"]
    assert any(row["user_id"] == member_user_id for row in items)

    patch_membership = client.patch(
        f"/v1/studio/team-memberships/{membership_id}",
        headers=admin_headers,
        json={"role": "lead"},
    )
    assert patch_membership.status_code == 200
    assert patch_membership.json()["data"]["role"] == "lead"
