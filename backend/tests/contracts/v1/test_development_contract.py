from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def _org_headers(client: TestClient, *, email: str, org_name: str, org_slug: str) -> tuple[dict[str, str], str]:
    headers = register_and_login(client, email=email)
    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": org_name, "slug": org_slug, "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]
    scoped = dict(headers)
    scoped["X-Org-ID"] = org_id
    return scoped, org_id


def test_development_workspace_and_runner_capabilities_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="development.capabilities@myai.dev",
        org_name="Development Capability Org",
        org_slug="development-capability-org",
    )

    workspace = client.post(
        "/v1/studio/workspaces",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "MyAIDE Workspace",
            "kind": "development",
            "description": "Workspace for development capability tests",
            "metadata": {
                "runner_id": "runner_local_01",
                "repo_name": "project-a",
                "repo_root": "C:/code/project-a",
                "primary_language": "python",
            },
        },
    )
    assert workspace.status_code == 200
    workspace_id = workspace.json()["data"]["workspace_id"]

    ingest = client.post(
        "/v1/knowledge/code-ingest",
        headers=headers,
        json={
            "org_id": org_id,
            "workspace_id": workspace_id,
            "runner_id": "runner_local_01",
            "project": {
                "title": "Project A",
                "project_key": "proj-a",
                "repo_name": "project-a",
                "repo_root": "C:/code/project-a"
            },
            "files": [
                {
                    "path": "src/helpers.py",
                    "language": "python",
                    "symbols": [
                        {"name": "normalize_helper", "symbol_kind": "function"}
                    ]
                }
            ]
        },
    )
    assert ingest.status_code == 200

    workspace_caps = client.get(f"/v1/development/workspaces/{workspace_id}/capabilities", headers=headers)
    assert workspace_caps.status_code == 200
    workspace_data = workspace_caps.json()["data"]
    assert workspace_data["workspaceId"] == workspace_id
    assert workspace_data["runnerId"] == "runner_local_01"
    keys = {item["key"] for item in workspace_data["capabilities"]}
    assert "workspace.search" in keys
    assert "source.profile.upsert" in keys
    assert "workspace.code_index" in keys
    assert "language.python.lsp" in keys
    assert "repo.status" in keys

    runner_caps = client.get("/v1/development/runners/runner_local_01/capabilities", headers=headers)
    assert runner_caps.status_code == 200
    runner_data = runner_caps.json()["data"]
    assert runner_data["runnerId"] == "runner_local_01"
    assert workspace_id in runner_data["summary"]["workspace_ids"]
    runner_keys = {item["key"] for item in runner_data["capabilities"]}
    assert "workspace.code_index" in runner_keys
    assert "language.python.lsp" in runner_keys


def test_development_capability_resolution_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="development.resolve@myai.dev",
        org_name="Development Resolve Org",
        org_slug="development-resolve-org",
    )

    workspace = client.post(
        "/v1/studio/workspaces",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Resolve Workspace",
            "kind": "development",
            "metadata": {
                "runner_id": "runner_local_02",
                "repo_name": "project-b",
                "repo_root": "C:/code/project-b",
                "primary_language": "python",
                "policy": {
                    "blocked_capabilities": ["workspace.patch.apply"],
                    "proposal_only_capabilities": ["repo.checkout"],
                },
            },
        },
    )
    assert workspace.status_code == 200
    workspace_id = workspace.json()["data"]["workspace_id"]

    resolve = client.post(
        "/v1/development/capabilities/resolve",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "required_capabilities": [
                "workspace.search",
                "language.python.lsp",
                "workspace.patch.apply",
                "repo.checkout",
            ],
        },
    )
    assert resolve.status_code == 200
    data = resolve.json()["data"]
    assert data["allow"] is False
    by_key = {item["key"]: item for item in data["results"]}
    assert by_key["workspace.search"]["resolution"] == "ready"
    assert by_key["language.python.lsp"]["resolution"] == "install_required"
    assert by_key["workspace.patch.apply"]["status"] == "blocked_by_policy"
    assert by_key["repo.checkout"]["resolution"] == "proposal_only"


def test_development_policy_check_contract() -> None:
    client = TestClient(app)
    headers, org_id = _org_headers(
        client,
        email="development.policy.check@myai.dev",
        org_name="Development Policy Org",
        org_slug="development-policy-org",
    )

    workspace = client.post(
        "/v1/studio/workspaces",
        headers=headers,
        json={
            "org_id": org_id,
            "name": "Policy Workspace",
            "kind": "development",
            "metadata": {
                "runner_id": "runner_local_policy",
                "repo_name": "project-policy",
                "repo_root": "C:/code/project-policy",
                "policy": {
                    "path_rules": [
                        {
                            "pathRuleId": "infra-proposal-only",
                            "matchType": "glob",
                            "pattern": "infra/**",
                            "read": "allow",
                            "write": "deny",
                            "proposal": "allow"
                        }
                    ]
                },
            },
        },
    )
    assert workspace.status_code == 200
    workspace_id = workspace.json()["data"]["workspace_id"]

    apply_check = client.post(
        "/v1/policy/development/check",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "session_id": "sess_1",
            "capability": "workspace.patch.apply",
            "targets": [{"kind": "path", "value": "infra/deploy.yaml"}],
            "mode": "build",
        },
    )
    assert apply_check.status_code == 200
    apply_data = apply_check.json()["data"]
    assert apply_data["allow"] is False
    assert apply_data["reason_code"] == "POLICY_DEVELOPMENT_PROPOSAL_REQUIRED"
    assert apply_data["target_decisions"][0]["decision"] == "proposal_required"

    propose_check = client.post(
        "/v1/policy/development/check",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "session_id": "sess_1",
            "capability": "workspace.patch.propose",
            "targets": [{"kind": "path", "value": "infra/deploy.yaml"}],
            "mode": "build",
        },
    )
    assert propose_check.status_code == 200
    propose_data = propose_check.json()["data"]
    assert propose_data["allow"] is True
    assert propose_data["reason_code"] == "POLICY_DEVELOPMENT_ALLOW"
    assert propose_data["target_decisions"][0]["decision"] == "allow"
