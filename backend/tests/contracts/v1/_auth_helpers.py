from __future__ import annotations

from fastapi.testclient import TestClient


def register_and_login(
    client: TestClient,
    *,
    tenant_id: str = "tenant0",
    org_id: str | None = None,
    email: str = "bootstrap.admin@myai.dev",
    password: str = "Password123!",
    is_global_admin: bool = True,
    scope_org_id: str | None = None,
) -> dict[str, str]:
    tenant_status = client.get("/v1/bootstrap/tenant/status")
    assert tenant_status.status_code == 200
    tenant_data = tenant_status.json()["data"]
    if not tenant_data["configured"]:
        bootstrap = client.post(
            "/v1/bootstrap/tenant",
            json={"tenant_id": tenant_id, "name": "Test Tenant"},
        )
        assert bootstrap.status_code == 200

    auth_status = client.get("/v1/auth/status", headers={"X-Tenant-ID": tenant_id})
    assert auth_status.status_code == 200
    admin_configured = bool(auth_status.json()["data"]["admin_configured"])

    register_payload: dict[str, object] = {
        "tenant_id": tenant_id,
        "email": email,
        "password": password,
        "first_name": "Owner",
        "last_name": "User",
        "is_global_admin": is_global_admin and not admin_configured,
    }
    registration_org_id = org_id or (scope_org_id if admin_configured else None)
    if registration_org_id is not None:
        register_payload["org_id"] = registration_org_id

    register_response = client.post("/v1/auth/register", json=register_payload)
    assert register_response.status_code == 200

    login_payload: dict[str, object] = {
        "tenant_id": tenant_id,
        "email": email,
        "password": password,
    }
    if org_id is not None:
        login_payload["org_id"] = org_id

    login_response = client.post("/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": "test-correlation-id",
        "X-Tenant-ID": tenant_id,
    }
    if scope_org_id is not None:
        headers["X-Org-ID"] = scope_org_id
    return headers
