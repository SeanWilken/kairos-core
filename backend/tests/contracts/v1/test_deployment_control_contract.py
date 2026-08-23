from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


DIGEST_A = f"sha256:{'a' * 64}"
DIGEST_B = f"sha256:{'b' * 64}"


def _org_headers(client: TestClient, *, slug: str = "deployment-org") -> tuple[dict[str, str], str]:
    headers = register_and_login(client, email=f"{slug}@myai.dev")
    response = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": slug.replace("-", " ").title(), "slug": slug, "mode": "team"},
    )
    assert response.status_code == 200
    org_id = response.json()["data"]["org_id"]
    scoped = dict(headers)
    scoped["X-Org-ID"] = org_id
    return scoped, org_id


def _create_registry(client: TestClient, headers: dict[str, str], org_id: str) -> dict:
    response = client.post(
        "/v1/deployment-control/registry-connections",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Docker Hub",
            "provider": "docker_hub",
            "registry_url": "https://index.docker.io",
            "namespace": "myaitech",
            "credential_secret_ref": "vault://deployment/docker-hub",
            "config": {"supports_immutable_digests": True},
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _create_environment(client: TestClient, headers: dict[str, str], org_id: str) -> dict:
    response = client.post(
        "/v1/deployment-control/environments",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Production",
            "slug": "production",
            "environment_type": "production",
            "config": {"runner_id": "runner_prod_01", "deployment_adapter": "terraform"},
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _create_release(
    client: TestClient,
    headers: dict[str, str],
    org_id: str,
    registry_connection_id: str,
    *,
    version: str,
    digest: str,
) -> dict:
    response = client.post(
        "/v1/deployment-control/releases",
        headers=headers,
        json={
            "org_id": org_id,
            "registry_connection_id": registry_connection_id,
            "component": "core-api",
            "version": version,
            "artifact_type": "container",
            "artifact_ref": f"docker.io/myaitech/core-api@{digest}",
            "artifact_digest": digest,
            "channel": "candidate",
            "migration_plan": {
                "strategy": "expand",
                "migration_ids": ["0027_deployment_control_plane"],
                "backward_compatible": True,
                "requires_backup": False,
                "validation_checks": ["schema-present", "row-count-stable"],
            },
            "rollback_instructions": "Redeclare the previous immutable release; do not reverse the additive migration.",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_deployment_control_declarative_lifecycle() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(client)

    registry = _create_registry(client, headers, org_id)
    assert registry["credential_secret_ref"] == "vault://deployment/docker-hub"
    assert "password" not in registry
    environment = _create_environment(client, headers, org_id)
    explicit_scope_headers = dict(headers)
    explicit_scope_headers.pop("X-Org-ID")
    explicit_scope = client.get(
        "/v1/deployment-control/environments",
        headers=explicit_scope_headers,
        params={"org_id": org_id},
    )
    assert explicit_scope.status_code == 200
    release_one = _create_release(
        client,
        headers,
        org_id,
        registry["registry_connection_id"],
        version="0.2.0-rc.1",
        digest=DIGEST_A,
    )
    assert release_one["artifact_digest"] == DIGEST_A
    assert release_one["migration_plan"]["strategy"] == "expand"

    deployment_one_response = client.post(
        "/v1/deployment-control/deployments",
        headers=headers,
        json={
            "org_id": org_id,
            "environment_id": environment["environment_id"],
            "release_id": release_one["release_id"],
            "desired_state": {"replicas": 1, "approval_policy": "explicit"},
        },
    )
    assert deployment_one_response.status_code == 200
    deployment_one = deployment_one_response.json()["data"]
    assert deployment_one["status"] == "declared"
    assert deployment_one["is_current"] is True

    check_response = client.post(
        f"/v1/deployment-control/deployments/{deployment_one['deployment_id']}/runtime-check-runs",
        headers=headers,
        json={
            "org_id": org_id,
            "status": "pass",
            "source": "operator",
            "checks": [{"key": "health", "status": "pass"}],
            "summary": {"passed": 1, "failed": 0},
        },
    )
    assert check_response.status_code == 200
    assert check_response.json()["data"]["status"] == "pass"

    forged_runner_check = client.post(
        f"/v1/deployment-control/deployments/{deployment_one['deployment_id']}/runtime-check-runs",
        headers=headers,
        json={
            "org_id": org_id,
            "status": "pass",
            "source": "myaide_runner",
        },
    )
    assert forged_runner_check.status_code == 422

    release_two = _create_release(
        client,
        headers,
        org_id,
        registry["registry_connection_id"],
        version="0.2.0-rc.2",
        digest=DIGEST_B,
    )
    deployment_two_response = client.post(
        "/v1/deployment-control/deployments",
        headers=headers,
        json={
            "org_id": org_id,
            "environment_id": environment["environment_id"],
            "release_id": release_two["release_id"],
        },
    )
    assert deployment_two_response.status_code == 200
    deployment_two = deployment_two_response.json()["data"]
    assert deployment_two["supersedes_deployment_id"] == deployment_one["deployment_id"]

    history = client.get(
        "/v1/deployment-control/deployments",
        headers=headers,
        params={"org_id": org_id, "environment_id": environment["environment_id"]},
    )
    assert history.status_code == 200
    by_id = {item["deployment_id"]: item for item in history.json()["data"]["items"]}
    assert by_id[deployment_one["deployment_id"]]["status"] == "superseded"
    assert by_id[deployment_one["deployment_id"]]["is_current"] is False

    current = client.get(
        "/v1/deployment-control/deployments",
        headers=headers,
        params={"org_id": org_id, "environment_id": environment["environment_id"], "current_only": True},
    )
    assert current.status_code == 200
    assert [item["deployment_id"] for item in current.json()["data"]["items"]] == [deployment_two["deployment_id"]]

    checks = client.get(
        f"/v1/deployment-control/deployments/{deployment_one['deployment_id']}/runtime-check-runs",
        headers=headers,
        params={"org_id": org_id},
    )
    assert checks.status_code == 200
    assert len(checks.json()["data"]["items"]) == 1

    audit = client.get("/v1/system/audit/events", headers=headers)
    assert audit.status_code == 200
    deployment_events = [
        item for item in audit.json()["data"]["items"] if item["action"].startswith("deployment.")
    ]
    assert deployment_events
    assert all(item["org_id"] == org_id for item in deployment_events)
    assert all(item["metadata"]["org_id"] == org_id for item in deployment_events)


def test_deployment_control_rejects_secrets_unsafe_contracts_and_duplicates() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(client, slug="deployment-safety-org")

    secret_config = client.post(
        "/v1/deployment-control/registry-connections",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Unsafe",
            "provider": "custom",
            "registry_url": "https://registry.example.com",
            "config": {"password": "must-not-persist"},
        },
    )
    assert secret_config.status_code == 422

    credential_url = client.post(
        "/v1/deployment-control/registry-connections",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Credential URL",
            "provider": "custom",
            "registry_url": "https://user:token@registry.example.com",
        },
    )
    assert credential_url.status_code == 422

    raw_credential = client.post(
        "/v1/deployment-control/registry-connections",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Raw Credential",
            "provider": "custom",
            "registry_url": "https://registry.example.com",
            "credential_secret_ref": "plain-text-token",
        },
    )
    assert raw_credential.status_code == 422

    registry = _create_registry(client, headers, org_id)
    unsafe_contract = client.post(
        "/v1/deployment-control/releases",
        headers=headers,
        json={
            "org_id": org_id,
            "registry_connection_id": registry["registry_connection_id"],
            "component": "core-api",
            "version": "1.0.0-contract",
            "artifact_ref": f"docker.io/myaitech/core-api@{DIGEST_A}",
            "artifact_digest": DIGEST_A,
            "migration_plan": {"strategy": "contract"},
        },
    )
    assert unsafe_contract.status_code == 422

    mutable_reference = client.post(
        "/v1/deployment-control/releases",
        headers=headers,
        json={
            "org_id": org_id,
            "registry_connection_id": registry["registry_connection_id"],
            "component": "core-api",
            "version": "mutable",
            "artifact_ref": "docker.io/myaitech/core-api:stable",
            "artifact_digest": DIGEST_A,
        },
    )
    assert mutable_reference.status_code == 422

    _create_release(
        client,
        headers,
        org_id,
        registry["registry_connection_id"],
        version="0.2.0",
        digest=DIGEST_A,
    )
    duplicate = client.post(
        "/v1/deployment-control/releases",
        headers=headers,
        json={
            "org_id": org_id,
            "registry_connection_id": registry["registry_connection_id"],
            "component": "core-api",
            "version": "0.2.0",
            "artifact_ref": f"docker.io/myaitech/core-api@{DIGEST_B}",
            "artifact_digest": DIGEST_B,
        },
    )
    assert duplicate.status_code == 409

    immutable_patch = client.patch(
        "/v1/deployment-control/releases/not-editable",
        headers=headers,
        json={"org_id": org_id, "artifact_digest": DIGEST_B},
    )
    assert immutable_patch.status_code == 405


def test_deployment_control_requires_active_org_membership() -> None:
    client = TestClient(app)
    owner_headers, org_id = _org_headers(client, slug="deployment-membership-org")
    assert owner_headers
    outsider_headers = register_and_login(
        client,
        email="deployment.outsider@myai.dev",
        is_global_admin=False,
    )
    outsider_headers["X-Org-ID"] = org_id

    response = client.get(
        "/v1/deployment-control/environments",
        headers=outsider_headers,
        params={"org_id": org_id},
    )
    assert response.status_code == 403
    assert response.json()["error"]["details"]["reason_code"] == "ORG_SCOPE_FORBIDDEN"

    audit_response = client.get("/v1/system/audit/events", headers=outsider_headers)
    assert audit_response.status_code == 403


def test_deployment_control_has_no_execution_routes() -> None:
    client = TestClient(app)
    specification = client.get("/openapi.json").json()
    paths = specification["paths"]
    forbidden = [
        "/v1/deployment-control/deploy",
        "/v1/deployment-control/execute",
        "/v1/deployment-control/apply",
        "/v1/deployment-control/rollback",
        "/v1/deployment-control/promote",
    ]
    assert all(path not in paths for path in forbidden)
    list_environments = paths["/v1/deployment-control/environments"]["get"]
    assert list_environments["security"] == [{"HTTPBearer": []}]
    success_schema = list_environments["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in success_schema
