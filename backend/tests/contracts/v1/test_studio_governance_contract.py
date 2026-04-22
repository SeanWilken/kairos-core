from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_studio_governance_baseline_and_settings_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="gov.owner@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Governance Org", "slug": "governance-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    baseline = client.get(f"/v1/studio/governance/baseline?org_id={org_id}", headers=headers)
    assert baseline.status_code == 200
    baseline_body = baseline.json()
    assert baseline_body["error"] is None
    assert baseline_body["data"]["org_id"] == org_id
    assert baseline_body["data"]["onboarding"]["status"] == "pending"

    patch_response = client.patch(
        "/v1/studio/settings",
        headers=headers,
        json={"org_id": org_id, "settings": {"invite_policy": "admin_only"}},
    )
    assert patch_response.status_code == 200
    patch_body = patch_response.json()
    assert patch_body["data"]["settings"]["invite_policy"] == "admin_only"

    get_response = client.get(f"/v1/studio/settings?org_id={org_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["data"]["settings"]["invite_policy"] == "admin_only"


def test_studio_invite_accept_contract() -> None:
    client = TestClient(app)
    owner_headers = register_and_login(client, email="invite.owner@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=owner_headers,
        json={"name": "Invite Org", "slug": "invite-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    invited_email = "invite.member@kairos.dev"
    invite_response = client.post(
        "/v1/studio/invites",
        headers=owner_headers,
        json={"org_id": org_id, "email": invited_email, "role": "member"},
    )
    assert invite_response.status_code == 200
    invite_id = invite_response.json()["data"]["invite_id"]

    invitee_headers = register_and_login(client, email=invited_email)
    accept_response = client.post(
        f"/v1/studio/invites/{invite_id}/accept",
        headers=invitee_headers,
        json={"org_id": org_id},
    )

    assert accept_response.status_code == 200
    accept_body = accept_response.json()
    assert accept_body["error"] is None
    assert accept_body["data"]["invite"]["status"] == "accepted"
    assert accept_body["data"]["membership"]["org_id"] == org_id


def test_studio_onboarding_complete_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="onboarding.owner@kairos.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Onboarding Org", "slug": "onboarding-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    complete_response = client.post(
        "/v1/studio/onboarding/complete",
        headers=headers,
        json={
            "org_id": org_id,
            "checklist": {
                "members_invited": True,
                "settings_reviewed": True,
                "persona_configured": True,
            },
        },
    )
    assert complete_response.status_code == 200
    complete_body = complete_response.json()
    assert complete_body["data"]["status"] == "completed"

    status_response = client.get(f"/v1/studio/onboarding/status?org_id={org_id}", headers=headers)
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["data"]["status"] == "completed"
    assert status_body["data"]["checklist"]["members_invited"] is True
