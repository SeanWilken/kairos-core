from __future__ import annotations

from fastapi.testclient import TestClient


def register_and_login(
    client: TestClient,
    *,
    tenant_id: str = "tenant0",
    org_id: str | None = None,
    email: str = "bootstrap.admin@kairos.dev",
    password: str = "Password123!",
    is_global_admin: bool = True,
    scope_org_id: str | None = None,
) -> dict[str, str]:
    register_payload: dict[str, object] = {
        "tenant_id": tenant_id,
        "email": email,
        "password": password,
        "first_name": "Owner",
        "last_name": "User",
        "is_global_admin": is_global_admin,
    }
    if org_id is not None:
        register_payload["org_id"] = org_id

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
