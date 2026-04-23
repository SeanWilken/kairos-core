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
    _bootstrap_tenant(client)

    register = client.post(
        "/v1/auth/register",
        json={
            "tenant_id": "tenant0",
            "email": "admin@kairos.dev",
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

    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_id": "tenant0",
            "email": "admin@kairos.dev",
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
    assert me_body["data"]["user"]["email"] == "admin@kairos.dev"

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
            "email": "operator@kairos.dev",
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
            "email": "operator@kairos.dev",
            "password": "WrongPassword123!",
        },
    )
    assert login.status_code == 401
    body = login.json()
    assert body["error"]["details"]["reason_code"] == "AUTH_INVALID_CREDENTIALS"
