from __future__ import annotations

from typing import Any
import fnmatch


def _normalize_provider(provider_id: str | None) -> str:
    value = str(provider_id or "").strip().lower()
    if value == "gemini":
        return "google"
    return value or "openai"


def _clean_lines(items: list[Any]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _xml_tag(tag: str, value: str) -> str:
    escaped = (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    return f"<{tag}>{escaped}</{tag}>"


def _anthropic_xml_payload(resume: dict[str, Any], metadata: dict[str, Any]) -> str:
    traits = _clean_lines(resume.get("traits", []))
    expertise = _clean_lines(resume.get("expertise", []))
    tools = _clean_lines(resume.get("tools", []))
    do_list = _clean_lines((resume.get("guidelines", {}) or {}).get("do_list", []))
    dont_list = _clean_lines((resume.get("guidelines", {}) or {}).get("dont_list", []))
    guardrails = _clean_lines((resume.get("guidelines", {}) or {}).get("guardrails", []))

    lines = [
        "<persona_resume>",
        _xml_tag("persona_name", str(resume.get("persona_name", ""))),
        _xml_tag("role", str(resume.get("role", ""))),
        _xml_tag("summary", str(resume.get("summary", ""))),
        _xml_tag("communication_style", str(resume.get("communication_style", "balanced"))),
        _xml_tag("initiative_level", str(resume.get("initiative_level", "moderate"))),
        "<traits>",
    ]
    lines.extend([_xml_tag("trait", item) for item in traits])
    lines.append("</traits>")
    lines.append("<expertise>")
    lines.extend([_xml_tag("skill", item) for item in expertise])
    lines.append("</expertise>")
    lines.append("<tools>")
    lines.extend([_xml_tag("tool", item) for item in tools])
    lines.append("</tools>")
    lines.append("<guidelines>")
    lines.append("<do_list>")
    lines.extend([_xml_tag("item", item) for item in do_list])
    lines.append("</do_list>")
    lines.append("<dont_list>")
    lines.extend([_xml_tag("item", item) for item in dont_list])
    lines.append("</dont_list>")
    lines.append("<guardrails>")
    lines.extend([_xml_tag("item", item) for item in guardrails])
    lines.append("</guardrails>")
    lines.append("</guidelines>")
    lines.append("<metadata>")
    lines.append(_xml_tag("version", str(metadata.get("version", "1.0.0"))))
    lines.append(_xml_tag("approval_status", str(metadata.get("approval_status", "draft"))))
    lines.append("</metadata>")
    lines.append("</persona_resume>")
    return "\n".join(lines)


def _openai_text_payload(resume: dict[str, Any], metadata: dict[str, Any]) -> str:
    traits = ", ".join(_clean_lines(resume.get("traits", []))) or "none"
    expertise = ", ".join(_clean_lines(resume.get("expertise", []))) or "none"
    tools = ", ".join(_clean_lines(resume.get("tools", []))) or "none"
    guidelines = resume.get("guidelines", {}) if isinstance(resume.get("guidelines"), dict) else {}
    do_list = "; ".join(_clean_lines(guidelines.get("do_list", []))) or "none"
    dont_list = "; ".join(_clean_lines(guidelines.get("dont_list", []))) or "none"
    guardrails = "; ".join(_clean_lines(guidelines.get("guardrails", []))) or "none"
    return "\n".join(
        [
            "Persona Resume Context",
            f"Name: {resume.get('persona_name', '')}",
            f"Role: {resume.get('role', '')}",
            f"Summary: {resume.get('summary', '')}",
            f"Communication Style: {resume.get('communication_style', 'balanced')}",
            f"Initiative Level: {resume.get('initiative_level', 'moderate')}",
            f"Traits: {traits}",
            f"Expertise: {expertise}",
            f"Tools: {tools}",
            f"Do: {do_list}",
            f"Avoid: {dont_list}",
            f"Guardrails: {guardrails}",
            f"Version: {metadata.get('version', '1.0.0')}",
            f"Approval Status: {metadata.get('approval_status', 'draft')}",
        ]
    )


def _google_json_payload(resume: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "persona": resume,
        "metadata": {
            "version": metadata.get("version", "1.0.0"),
            "approval_status": metadata.get("approval_status", "draft"),
        },
        "instructions": {
            "format": "json",
            "use": "prompt_context_injection",
        },
    }


def build_provider_resume_export(
    *,
    resume: dict[str, Any],
    metadata: dict[str, Any],
    provider_id: str | None,
    model_id: str | None,
    policy_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = _normalize_provider(provider_id)
    model = str(model_id or "").strip() or None

    configured_format: str | None = None
    policy = policy_config if isinstance(policy_config, dict) else {}
    rules = policy.get("provider_rules", []) if isinstance(policy.get("provider_rules"), list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_provider = _normalize_provider(str(rule.get("provider_id", "")))
        if rule_provider and rule_provider != provider:
            continue
        pattern = str(rule.get("model_pattern", "")).strip()
        if pattern and model and not fnmatch.fnmatch(model, pattern):
            continue
        fmt = str(rule.get("format", "")).strip().lower()
        if fmt in {"xml", "text", "json"}:
            configured_format = fmt
            break

    if configured_format == "xml":
        return {
            "provider_id": provider,
            "model_id": model,
            "format": "xml",
            "content": _anthropic_xml_payload(resume, metadata),
        }
    if configured_format == "json":
        return {
            "provider_id": provider,
            "model_id": model,
            "format": "json",
            "content": _google_json_payload(resume, metadata),
        }
    if configured_format == "text":
        return {
            "provider_id": provider,
            "model_id": model,
            "format": "text",
            "content": _openai_text_payload(resume, metadata),
        }

    if provider == "anthropic":
        return {
            "provider_id": provider,
            "model_id": model,
            "format": "xml",
            "content": _anthropic_xml_payload(resume, metadata),
        }
    if provider == "google":
        return {
            "provider_id": provider,
            "model_id": model,
            "format": "json",
            "content": _google_json_payload(resume, metadata),
        }
    return {
        "provider_id": provider,
        "model_id": model,
        "format": "text",
        "content": _openai_text_payload(resume, metadata),
    }
