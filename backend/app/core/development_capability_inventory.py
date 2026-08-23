from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.knowledge_contract_store import knowledge_contract_store
from app.core.tool_catalog import get_tool_runtime_registry


LANGUAGE_TOOL_PACKS: dict[str, list[dict[str, str]]] = {
    "python": [
        {"key": "language.python.lsp", "tool_pack_id": "python-core-pack"},
    ],
    "typescript": [
        {"key": "language.typescript.lsp", "tool_pack_id": "typescript-core-pack"},
        {"key": "lint.eslint", "tool_pack_id": "typescript-core-pack"},
        {"key": "format.prettier", "tool_pack_id": "typescript-core-pack"},
    ],
    "javascript": [
        {"key": "language.typescript.lsp", "tool_pack_id": "typescript-core-pack"},
        {"key": "lint.eslint", "tool_pack_id": "typescript-core-pack"},
        {"key": "format.prettier", "tool_pack_id": "typescript-core-pack"},
    ],
    "f#": [
        {"key": "language.fsharp.lsp", "tool_pack_id": "fsharp-core-pack"},
    ],
    "fsharp": [
        {"key": "language.fsharp.lsp", "tool_pack_id": "fsharp-core-pack"},
    ],
    "markdown": [
        {"key": "lint.markdown", "tool_pack_id": "markdown-core-pack"},
    ],
    "dockerfile": [
        {"key": "language.dockerfile.lsp", "tool_pack_id": "dockerfile-core-pack"},
    ],
}

TOOL_CAPABILITY_MAP: dict[str, list[str]] = {
    "pdf_generate": ["document.render"],
    "speech_to_text": ["speech_to_text"],
    "text_to_speech": ["text_to_speech"],
    "image_generate": ["image_generation"],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metadata_value(item: dict[str, Any], key: str) -> str:
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    state = item.get("state", {}) if isinstance(item.get("state"), dict) else {}
    return str(metadata.get(key) or state.get(key) or "").strip()


def _workspace_metadata(workspace: dict[str, Any]) -> dict[str, Any]:
    return workspace.get("metadata", {}) if isinstance(workspace.get("metadata", {}), dict) else {}


def _entity_workspace_id(entity: dict[str, Any]) -> str:
    facets = entity.get("facets", {}) if isinstance(entity.get("facets"), dict) else {}
    kind_payload = entity.get("kind_payload", {}) if isinstance(entity.get("kind_payload"), dict) else {}
    return str(facets.get("workspace_id") or kind_payload.get("workspace_id") or "").strip()


def _entity_runner_id(entity: dict[str, Any]) -> str:
    facets = entity.get("facets", {}) if isinstance(entity.get("facets"), dict) else {}
    kind_payload = entity.get("kind_payload", {}) if isinstance(entity.get("kind_payload"), dict) else {}
    return str(facets.get("runner_id") or kind_payload.get("runner_id") or "").strip()


def _entity_language(entity: dict[str, Any]) -> str:
    facets = entity.get("facets", {}) if isinstance(entity.get("facets"), dict) else {}
    kind_payload = entity.get("kind_payload", {}) if isinstance(entity.get("kind_payload"), dict) else {}
    return str(facets.get("language") or kind_payload.get("language") or "").strip().lower()


def _add_capability(items: dict[str, dict[str, Any]], *, key: str, status: str, source: str, provenance: dict[str, Any], tool_pack_id: str | None = None, version: str = "") -> None:
    existing = items.get(key)
    rank = {"available": 5, "installed": 4, "installable": 3, "degraded": 2, "unavailable": 1, "blocked_by_policy": 0}
    candidate = {
        "key": key,
        "status": status,
        "source": source,
        "provenance": provenance,
    }
    if tool_pack_id:
        candidate["toolPackId"] = tool_pack_id
    if version:
        candidate["version"] = version
    if existing is None or rank.get(status, -1) > rank.get(str(existing.get("status", "")), -1):
        items[key] = candidate


def _runtime_capabilities() -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    runtime_entries = get_tool_runtime_registry().get("items", []) if isinstance(get_tool_runtime_registry().get("items", []), list) else []
    for entry in runtime_entries:
        if not isinstance(entry, dict):
            continue
        tool_id = str(entry.get("tool_id", "")).strip()
        installed = bool(entry.get("installed", False))
        version = str(entry.get("version", "")).strip()
        provenance = {
            "implementation_id": entry.get("implementation_id"),
            "binary_path": entry.get("binary_path"),
            "validated": bool(entry.get("validated", False)),
        }
        if tool_id == "git_status":
            for key in ("repo.status", "repo.diff", "repo.log", "repo.fetch"):
                _add_capability(items, key=key, status=("installed" if installed else "unavailable"), source="native", provenance=provenance, version=version)
            continue
        for capability_key in TOOL_CAPABILITY_MAP.get(tool_id, []):
            _add_capability(items, key=capability_key, status=("installed" if installed else "degraded"), source="runtime_registry", provenance=provenance, version=version)
    return items


def _workspace_knowledge_entities(*, tenant_id: str, org_id: str, user_id: str, workspace_id: str | None = None, runner_id: str | None = None) -> list[dict[str, Any]]:
    items = knowledge_contract_store.list_visible_entities(tenant_id=tenant_id, org_id=org_id, user_id=user_id, limit=1000)
    filtered: list[dict[str, Any]] = []
    for item in items:
        entity_workspace_id = _entity_workspace_id(item)
        entity_runner_id = _entity_runner_id(item)
        if workspace_id and entity_workspace_id != workspace_id:
            continue
        if runner_id and entity_runner_id != runner_id:
            continue
        if workspace_id or runner_id:
            filtered.append(item)
    return filtered


def build_workspace_capability_profile(*, tenant_id: str, org_id: str, user_id: str, workspace: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(workspace.get("workspace_id", "")).strip()
    runner_id = _metadata_value(workspace, "runner_id") or workspace_id
    repo_name = _metadata_value(workspace, "repo_name")
    repo_root = _metadata_value(workspace, "repo_root")
    capability_map = _runtime_capabilities()
    knowledge_entities = _workspace_knowledge_entities(tenant_id=tenant_id, org_id=org_id, user_id=user_id, workspace_id=workspace_id)
    languages = {
        _entity_language(item)
        for item in knowledge_entities
        if _entity_language(item)
    }
    metadata = _workspace_metadata(workspace)
    orchestration_manifest = str(metadata.get("orchestration_manifest") or "").strip()
    workspace_languages = metadata.get("languages", []) if isinstance(metadata.get("languages", []), list) else []
    if isinstance(workspace_languages, list):
        languages.update(str(item).strip().lower() for item in workspace_languages if str(item).strip())
    primary_language = _metadata_value(workspace, "primary_language")
    if primary_language:
        languages.add(primary_language.lower())

    _add_capability(capability_map, key="workspace.search", status="available", source="core", provenance={"workspace_id": workspace_id})
    _add_capability(capability_map, key="workspace.patch.propose", status="available", source="core", provenance={"workspace_id": workspace_id})
    _add_capability(capability_map, key="workspace.patch.apply", status="available", source="core", provenance={"workspace_id": workspace_id})
    _add_capability(capability_map, key="source.profile.upsert", status="available", source="knowledge_graph", provenance={"workspace_id": workspace_id})
    if repo_name or repo_root:
        _add_capability(capability_map, key="repo.checkout", status="available", source="workspace_metadata", provenance={"repo_name": repo_name, "repo_root": repo_root})
        _add_capability(capability_map, key="repo.pull_latest", status="available", source="workspace_metadata", provenance={"repo_name": repo_name, "repo_root": repo_root})
    if orchestration_manifest:
        orchestration_provenance = {
            "workspace_id": workspace_id,
            "runner_id": runner_id,
            "manifest": orchestration_manifest,
            "executor": "myaide_runner",
            "attestation_required": True,
        }
        for key in (
            "workspace.pipeline.run",
            "repo.sync",
            "container.images.refresh",
            "container.stack.deploy",
            "database.migrations.status",
            "database.migrations.apply",
        ):
            _add_capability(capability_map, key=key, status="degraded", source="workspace_metadata", provenance=orchestration_provenance)
    if knowledge_entities:
        _add_capability(capability_map, key="workspace.code_index", status="available", source="knowledge_graph", provenance={"entity_count": len(knowledge_entities)})
    for language in sorted(languages):
        for item in LANGUAGE_TOOL_PACKS.get(language, []):
            _add_capability(
                capability_map,
                key=item["key"],
                status="installable",
                source="tool-pack",
                provenance={"language": language, "workspace_id": workspace_id},
                tool_pack_id=item["tool_pack_id"],
            )
    return {
        "workspaceId": workspace_id,
        "runnerId": runner_id,
        "snapshotAt": _now_iso(),
        "capabilities": sorted(capability_map.values(), key=lambda item: str(item.get("key", ""))),
        "summary": {
            "repo_name": repo_name,
            "repo_root": repo_root,
            "orchestration_manifest": orchestration_manifest,
            "languages": sorted(languages),
            "knowledge_entity_count": len(knowledge_entities),
        },
    }


def resolve_capability_requirements(*, capability_profile: dict[str, Any], required_capabilities: list[str], workspace: dict[str, Any] | None = None) -> dict[str, Any]:
    capability_items = capability_profile.get("capabilities", []) if isinstance(capability_profile.get("capabilities", []), list) else []
    capability_map = {
        str(item.get("key", "")).strip(): item
        for item in capability_items
        if isinstance(item, dict) and str(item.get("key", "")).strip()
    }
    metadata = _workspace_metadata(workspace or {}) if isinstance(workspace, dict) else {}
    policy = metadata.get("policy", {}) if isinstance(metadata.get("policy", {}), dict) else {}
    blocked_capabilities = {
        str(item).strip()
        for item in policy.get("blocked_capabilities", [])
        if str(item).strip()
    }
    protected_capabilities = {
        str(item).strip()
        for item in policy.get("proposal_only_capabilities", [])
        if str(item).strip()
    }
    results: list[dict[str, Any]] = []
    allow = True
    blocked_reasons: list[str] = []
    missing_reasons: list[str] = []
    installable_reasons: list[str] = []
    for capability in [str(item).strip() for item in required_capabilities if str(item).strip()]:
        if capability in blocked_capabilities or "*" in blocked_capabilities:
            allow = False
            blocked_reasons.append(capability)
            results.append(
                {
                    "key": capability,
                    "status": "blocked_by_policy",
                    "resolution": "blocked",
                    "reason_code": "DEVELOPMENT_CAPABILITY_BLOCKED_BY_POLICY",
                    "provenance": {"source": "workspace_policy", "policy": policy},
                }
            )
            continue
        item = capability_map.get(capability)
        if item is None:
            allow = False
            missing_reasons.append(capability)
            results.append(
                {
                    "key": capability,
                    "status": "unavailable",
                    "resolution": "missing",
                    "reason_code": "DEVELOPMENT_CAPABILITY_UNAVAILABLE",
                    "provenance": {"source": "capability_inventory"},
                }
            )
            continue
        status = str(item.get("status", "unavailable")).strip()
        if capability in protected_capabilities:
            allow = False
            results.append(
                {
                    "key": capability,
                    "status": status,
                    "resolution": "proposal_only",
                    "reason_code": "DEVELOPMENT_CAPABILITY_PROPOSAL_ONLY",
                    "provenance": item.get("provenance", {}),
                }
            )
            continue
        if status in {"available", "installed"}:
            results.append(
                {
                    "key": capability,
                    "status": status,
                    "resolution": "ready",
                    "reason_code": "DEVELOPMENT_CAPABILITY_READY",
                    "provenance": item.get("provenance", {}),
                }
            )
            continue
        if status == "installable":
            allow = False
            installable_reasons.append(capability)
            results.append(
                {
                    "key": capability,
                    "status": status,
                    "resolution": "install_required",
                    "reason_code": "DEVELOPMENT_CAPABILITY_INSTALL_REQUIRED",
                    "toolPackId": item.get("toolPackId"),
                    "provenance": item.get("provenance", {}),
                }
            )
            continue
        allow = False
        missing_reasons.append(capability)
        results.append(
            {
                "key": capability,
                "status": status,
                "resolution": "missing",
                "reason_code": "DEVELOPMENT_CAPABILITY_UNAVAILABLE",
                "provenance": item.get("provenance", {}),
            }
        )
    return {
        "allow": allow,
        "results": results,
        "summary": {
            "ready": len([item for item in results if item.get("resolution") == "ready"]),
            "proposal_only": len([item for item in results if item.get("resolution") == "proposal_only"]),
            "blocked": len(blocked_reasons),
            "install_required": len(installable_reasons),
            "missing": len(missing_reasons),
        },
    }


def build_runner_capability_profile(*, tenant_id: str, org_id: str, user_id: str, runner_id: str, workspaces: list[dict[str, Any]]) -> dict[str, Any]:
    capability_map = _runtime_capabilities()
    workspace_ids: list[str] = []
    languages: set[str] = set()
    for workspace in workspaces:
        if (_metadata_value(workspace, "runner_id") or str(workspace.get("workspace_id", "")).strip()) != runner_id:
            continue
        workspace_ids.append(str(workspace.get("workspace_id", "")).strip())
        profile = build_workspace_capability_profile(tenant_id=tenant_id, org_id=org_id, user_id=user_id, workspace=workspace)
        for capability in profile.get("capabilities", []):
            if isinstance(capability, dict):
                _add_capability(
                    capability_map,
                    key=str(capability.get("key", "")).strip(),
                    status=str(capability.get("status", "")).strip(),
                    source=str(capability.get("source", "")).strip(),
                    provenance=capability.get("provenance", {}) if isinstance(capability.get("provenance", {}), dict) else {},
                    tool_pack_id=str(capability.get("toolPackId", "")).strip() or None,
                    version=str(capability.get("version", "")).strip(),
                )
        summary = profile.get("summary", {}) if isinstance(profile.get("summary", {}), dict) else {}
        languages.update(str(item).strip().lower() for item in summary.get("languages", []) if str(item).strip())
    knowledge_entities = _workspace_knowledge_entities(tenant_id=tenant_id, org_id=org_id, user_id=user_id, runner_id=runner_id)
    if knowledge_entities:
        _add_capability(capability_map, key="workspace.code_index", status="available", source="knowledge_graph", provenance={"entity_count": len(knowledge_entities), "runner_id": runner_id})
    return {
        "runnerId": runner_id,
        "snapshotAt": _now_iso(),
        "capabilities": sorted(capability_map.values(), key=lambda item: str(item.get("key", ""))),
        "summary": {
            "workspace_ids": sorted({item for item in workspace_ids if item}),
            "languages": sorted(languages),
            "knowledge_entity_count": len(knowledge_entities),
        },
    }
