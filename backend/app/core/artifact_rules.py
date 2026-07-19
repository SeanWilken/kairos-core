from __future__ import annotations

from typing import Any


def evaluate_artifact_rules(*, artifact: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    working = _deep_copy_artifact(artifact)
    matched: list[dict[str, Any]] = []
    blocked = False
    review_required = False

    normalized_rules = sorted(
        [item for item in rules if isinstance(item, dict)],
        key=lambda item: int(item.get("priority", 100) or 100),
    )

    for rule in normalized_rules:
        if not _condition_matches(working, rule.get("condition", {})):
            continue
        action = rule.get("action", {}) if isinstance(rule.get("action"), dict) else {}
        action_type = str(action.get("type", "allow")).strip().lower() or "allow"
        matched.append(
            {
                "rule_id": str(rule.get("rule_id", "")).strip() or "rule",
                "action_type": action_type,
                "condition": rule.get("condition", {}),
            }
        )
        if action_type == "block":
            blocked = True
        elif action_type == "require_review":
            review_required = True
            _mark_review_required(working, action)
        elif action_type == "add_tag":
            _add_tag(working, str(action.get("tag", "")).strip())
        elif action_type == "set_facet":
            _set_facet(working, str(action.get("key", "")).strip(), action.get("value"))

    return {
        "blocked": blocked,
        "review_required": review_required,
        "matched_rules": matched,
        "artifact": working,
    }


def _deep_copy_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    tags = list(artifact.get("tags", [])) if isinstance(artifact.get("tags", []), list) else []
    facets = dict(artifact.get("facets", {})) if isinstance(artifact.get("facets", {}), dict) else {}
    quality = dict(artifact.get("quality", {})) if isinstance(artifact.get("quality", {}), dict) else {}
    kind_payload = dict(artifact.get("kind_payload", {})) if isinstance(artifact.get("kind_payload", {}), dict) else {}
    return {**artifact, "tags": tags, "facets": facets, "quality": quality, "kind_payload": kind_payload}


def _condition_matches(artifact: dict[str, Any], condition: Any) -> bool:
    if not isinstance(condition, dict):
        return False
    cond_type = str(condition.get("type", "")).strip().lower()
    config = condition.get("config", {}) if isinstance(condition.get("config"), dict) else {}
    if cond_type == "kind_is":
        return str(artifact.get("kind", "")).strip() == str(config.get("value", "")).strip()
    if cond_type == "kind_in":
        values = {str(item).strip() for item in config.get("values", []) if str(item).strip()} if isinstance(config.get("values"), list) else set()
        return str(artifact.get("kind", "")).strip() in values
    if cond_type == "subtype_is":
        subtype = _artifact_subtype(artifact)
        return subtype == str(config.get("value", "")).strip()
    if cond_type == "tag_present":
        tags = {str(item).strip().lower() for item in artifact.get("tags", []) if str(item).strip()} if isinstance(artifact.get("tags", []), list) else set()
        return str(config.get("value", "")).strip().lower() in tags
    if cond_type == "summary_contains":
        return str(config.get("value", "")).strip().lower() in str(artifact.get("summary", "")).lower()
    if cond_type == "content_contains":
        content = str((artifact.get("kind_payload", {}) or {}).get("content", "")) if isinstance(artifact.get("kind_payload", {}), dict) else ""
        return str(config.get("value", "")).strip().lower() in content.lower()
    if cond_type == "visibility_scope_is":
        visibility = artifact.get("visibility", {}) if isinstance(artifact.get("visibility"), dict) else {}
        return str(visibility.get("scope", "")).strip() == str(config.get("value", "")).strip()
    if cond_type == "relevancy_min":
        dimension = str(config.get("dimension", "")).strip()
        minimum = float(config.get("value", 0.0) or 0.0)
        return _relevancy_score(artifact, dimension) >= minimum
    return False


def _artifact_subtype(artifact: dict[str, Any]) -> str:
    facets = artifact.get("facets", {}) if isinstance(artifact.get("facets"), dict) else {}
    if str(facets.get("subtype", "")).strip():
        return str(facets.get("subtype", "")).strip()
    kind_payload = artifact.get("kind_payload", {}) if isinstance(artifact.get("kind_payload"), dict) else {}
    return str(kind_payload.get("subtype", "")).strip()


def _relevancy_score(artifact: dict[str, Any], dimension: str) -> float:
    if not dimension:
        return 0.0
    relevancy = artifact.get("relevancy", {}) if isinstance(artifact.get("relevancy"), dict) else {}
    value = relevancy.get(dimension)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        score = value.get("score", 0.0)
        if isinstance(score, (int, float)):
            return float(score)
    return 0.0


def _mark_review_required(artifact: dict[str, Any], action: dict[str, Any]) -> None:
    quality = artifact.get("quality", {}) if isinstance(artifact.get("quality"), dict) else {}
    quality["review_required"] = True
    quality["review_reason"] = str(action.get("reason", "rule_triggered")).strip() or "rule_triggered"
    artifact["quality"] = quality


def _add_tag(artifact: dict[str, Any], tag: str) -> None:
    if not tag:
        return
    tags = artifact.get("tags", []) if isinstance(artifact.get("tags", []), list) else []
    if tag not in tags:
        tags.append(tag)
    artifact["tags"] = tags


def _set_facet(artifact: dict[str, Any], key: str, value: Any) -> None:
    if not key:
        return
    facets = artifact.get("facets", {}) if isinstance(artifact.get("facets"), dict) else {}
    facets[key] = value
    artifact["facets"] = facets
