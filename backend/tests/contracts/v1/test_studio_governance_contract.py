from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_studio_governance_baseline_and_settings_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="gov.owner@myai.dev")

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
    owner_headers = register_and_login(client, email="invite.owner@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=owner_headers,
        json={"name": "Invite Org", "slug": "invite-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    invited_email = "invite.member@myai.dev"
    invite_response = client.post(
        "/v1/studio/invites",
        headers=owner_headers,
        json={"org_id": org_id, "email": invited_email, "role": "member"},
    )
    assert invite_response.status_code == 200
    invite_id = invite_response.json()["data"]["invite_id"]

    email_messages = client.get(
        "/v1/tools/email/messages",
        headers=owner_headers,
        params={"org_id": org_id},
    )
    assert email_messages.status_code == 200
    assert any(item["subject"].startswith("Invitation to join") for item in email_messages.json()["data"]["items"])

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
    headers = register_and_login(client, email="onboarding.owner@myai.dev")

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


def test_studio_governance_baseline_not_found_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="gov.notfound@myai.dev")

    response = client.get("/v1/studio/governance/baseline?org_id=missing-org", headers=headers)

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_NOT_FOUND"


def test_studio_invite_create_not_found_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="invite.notfound@myai.dev")

    response = client.post(
        "/v1/studio/invites",
        headers=headers,
        json={"org_id": "missing-org", "email": "person@myai.dev", "role": "member"},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_NOT_FOUND"


def test_studio_invite_accept_email_mismatch_contract() -> None:
    client = TestClient(app)
    owner_headers = register_and_login(client, email="invite.owner2@myai.dev")

    org_response = client.post(
        "/v1/studio/organizations",
        headers=owner_headers,
        json={"name": "Invite Mismatch Org", "slug": "invite-mismatch-org", "mode": "team"},
    )
    assert org_response.status_code == 200
    org_id = org_response.json()["data"]["org_id"]

    invite_response = client.post(
        "/v1/studio/invites",
        headers=owner_headers,
        json={"org_id": org_id, "email": "expected.member@myai.dev", "role": "member"},
    )
    assert invite_response.status_code == 200
    invite_id = invite_response.json()["data"]["invite_id"]

    mismatched_headers = register_and_login(client, email="different.member@myai.dev")
    accept_response = client.post(
        f"/v1/studio/invites/{invite_id}/accept",
        headers=mismatched_headers,
        json={"org_id": org_id},
    )

    assert accept_response.status_code == 403
    body = accept_response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_INVITE_EMAIL_MISMATCH"


def test_studio_onboarding_status_requires_org_context_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="onboarding.noorg@myai.dev")

    response = client.get("/v1/studio/onboarding/status", headers=headers)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_REQUIRED"


def test_studio_onboarding_complete_requires_org_context_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="onboarding.complete.noorg@myai.dev")

    response = client.post("/v1/studio/onboarding/complete", headers=headers, json={"checklist": {}})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_REQUIRED"


def test_studio_settings_patch_requires_org_context_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="settings.noorg@myai.dev")

    response = client.patch(
        "/v1/studio/settings",
        headers=headers,
        json={"settings": {"invite_policy": "admin_only"}},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["details"]["reason_code"] == "STUDIO_ORG_REQUIRED"
