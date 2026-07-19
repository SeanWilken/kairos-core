from fastapi.testclient import TestClient

from app.main import app


def _bootstrap_tenant(client: TestClient) -> None:
    status = client.get("/v1/bootstrap/tenant/status")
    assert status.status_code == 200
    if not status.json()["data"]["configured"]:
        created = client.post(
            "/v1/bootstrap/tenant",
            json={"tenant_id": "tenant0", "name": "Tenant Zero"},
        )
        assert created.status_code == 200


def test_auth_register_login_refresh_me_contract() -> None:
    client = TestClient(app)
    initial_status = client.get("/v1/auth/status")
    assert initial_status.status_code == 200
    assert initial_status.json()["data"]["tenant_configured"] is False
    assert initial_status.json()["data"]["admin_configured"] is False
    _bootstrap_tenant(client)

    tenant_status = client.get("/v1/auth/status", headers={"X-Tenant-ID": "tenant0"})
    assert tenant_status.status_code == 200
    assert tenant_status.json()["data"]["tenant_configured"] is True
    assert tenant_status.json()["data"]["admin_configured"] is False

    register = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "admin@myai.dev",
            "password": "Password123!",
            "first_name": "Admin",
            "last_name": "User",
            "is_global_admin": True,
        },
    )
    assert register.status_code == 200
    register_body = register.json()
    assert register_body["error"] is None
    assert isinstance(register_body["data"]["access_token"], str)
    assert isinstance(register_body["data"]["refresh_token"], str)

    locked_status = client.get("/v1/auth/status", headers={"X-Tenant-ID": "tenant0"})
    assert locked_status.status_code == 200
    assert locked_status.json()["data"]["admin_configured"] is True
    assert locked_status.json()["data"]["login_required"] is True

    second_admin = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "second-admin@myai.dev",
            "password": "Password123!",
            "first_name": "Second",
            "last_name": "Admin",
            "is_global_admin": True,
        },
    )
    assert second_admin.status_code == 403
    assert second_admin.json()["error"]["details"]["reason_code"] == "AUTH_ADMIN_BOOTSTRAP_LOCKED"

    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": "tenant0",
            "email": "admin@myai.dev",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200
    login_body = login.json()
    access_token = login_body["data"]["access_token"]
    refresh_token = login_body["data"]["refresh_token"]

    me = client.get(
        "/v1/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Correlation-ID": "test-correlation-id",
        },
    )
    assert me.status_code == 200
    me_body = me.json()
    assert me_body["error"] is None
    assert me_body["data"]["user"]["email"] == "admin@myai.dev"
    assert isinstance(me_body["data"].get("org_options", []), list)

    refreshed = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["error"] is None
    assert isinstance(refreshed_body["data"]["access_token"], str)
    assert refreshed_body["data"]["access_token"] != access_token


def test_auth_login_invalid_password_contract() -> None:
    client = TestClient(app)
    _bootstrap_tenant(client)
    seed = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "operator@myai.dev",
            "password": "Password123!",
            "first_name": "Ops",
            "last_name": "User",
            "is_global_admin": True,
        },
    )
    assert seed.status_code == 200

    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": "tenant0",
            "email": "operator@myai.dev",
            "password": "WrongPassword123!",
        },
    )
    assert login.status_code == 401
    body = login.json()
    assert body["error"]["details"]["reason_code"] == "AUTH_INVALID_CREDENTIALS"


def test_auth_login_without_tenant_payload_in_single_tenant_mode() -> None:
    client = TestClient(app)
    _bootstrap_tenant(client)
    seed = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "singletenant@myai.dev",
            "password": "Password123!",
            "first_name": "Single",
            "last_name": "Tenant",
            "is_global_admin": True,
        },
    )
    assert seed.status_code == 200

    login = client.post(
        "/v1/auth/login",
        json={
            "email": "singletenant@myai.dev",
            "password": "Password123!",
        },
    )
    assert login.status_code == 200
    assert isinstance(login.json()["data"]["access_token"], str)


def test_auth_context_switch_contract() -> None:
    client = TestClient(app)
    _bootstrap_tenant(client)

    register = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "switch.owner@myai.dev",
            "password": "Password123!",
            "first_name": "Switch",
            "last_name": "Owner",
            "is_global_admin": True,
        },
    )
    assert register.status_code == 200
    access_token = register.json()["data"]["access_token"]

    org1 = client.post(
        "/v1/studio/organizations",
        headers={"Authorization": f"Bearer {access_token}", "X-Correlation-ID": "test-correlation-id"},
        json={"name": "Switch Org A", "slug": "switch-org-a", "mode": "team"},
    )
    assert org1.status_code == 200
    assert isinstance(org1.json()["data"]["org_id"], str)

    org2 = client.post(
        "/v1/studio/organizations",
        headers={"Authorization": f"Bearer {access_token}", "X-Correlation-ID": "test-correlation-id"},
        json={"name": "Switch Org B", "slug": "switch-org-b", "mode": "team"},
    )
    assert org2.status_code == 200
    org2_id = org2.json()["data"]["org_id"]

    switched = client.post(
        "/v1/auth/context/switch",
        headers={"Authorization": f"Bearer {access_token}", "X-Correlation-ID": "test-correlation-id"},
        json={"org_id": org2_id},
    )
    assert switched.status_code == 200
    switched_data = switched.json()["data"]
    assert switched_data["org"]["org_id"] == org2_id
    assert isinstance(switched_data["access_token"], str)


def test_auth_me_global_admin_includes_tenant_org_options_without_memberships() -> None:
    client = TestClient(app)
    _bootstrap_tenant(client)

    register = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "global.options@myai.dev",
            "password": "Password123!",
            "first_name": "Global",
            "last_name": "Options",
            "is_global_admin": True,
        },
    )
    assert register.status_code == 200
    access_token = register.json()["data"]["access_token"]

    org_a = client.post(
        "/v1/studio/organizations",
        headers={"Authorization": f"Bearer {access_token}", "X-Correlation-ID": "test-correlation-id"},
        json={"name": "Global Org A", "slug": "global-org-a", "mode": "team"},
    )
    assert org_a.status_code == 200
    org_a_id = org_a.json()["data"]["org_id"]

    org_b = client.post(
        "/v1/studio/organizations",
        headers={"Authorization": f"Bearer {access_token}", "X-Correlation-ID": "test-correlation-id"},
        json={"name": "Global Org B", "slug": "global-org-b", "mode": "team"},
    )
    assert org_b.status_code == 200
    org_b_id = org_b.json()["data"]["org_id"]

    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}", "X-Correlation-ID": "test-correlation-id"},
    )
    assert me.status_code == 200
    data = me.json()["data"]
    assert data["auth"]["is_global_admin"] is True
    options = data.get("org_options", [])
    assert isinstance(options, list)
    option_ids = {item["org_id"] for item in options}
    assert org_a_id in option_ids
    assert org_b_id in option_ids
