from __future__ import annotations

from typing import Any

from app.core.prompt_template_renderer import render_template
from app.core.prompt_template_store import prompt_template_store


def _join_lines(items: list[str]) -> str:
    return "\n".join([item for item in items if item.strip()])


def compile_persona_system_prompt(persona: dict[str, Any]) -> str:
    explicit = str(persona.get("system_prompt", "")).strip()
    if explicit:
        return explicit

    data = persona.get("data", {})
    if not isinstance(data, dict):
        data = {}

    prompt_blocks = data.get("prompt_blocks", {})
    personality = data.get("personality", {})
    policies = data.get("operational_policies", {})

    lines: list[str] = []
    lines.append(
        f"You are {persona.get('name', 'Kairos Assistant')}, acting as {persona.get('role', 'assistant')}."
    )
    lines.append(f"Scope: {persona.get('scope', 'organization')}.")

    if isinstance(prompt_blocks, dict):
        mission = str(prompt_blocks.get("mission", "")).strip()
        instructions = str(prompt_blocks.get("instructions", "")).strip()
        guardrails = prompt_blocks.get("guardrails", [])
        if mission:
            lines.append(f"Core mission: {mission}")
        if instructions:
            lines.append(f"Base instructions: {instructions}")
        if isinstance(guardrails, list) and guardrails:
            lines.append("Guardrails: " + "; ".join(str(item) for item in guardrails))

    if isinstance(personality, dict):
        traits = personality.get("traits", [])
        if isinstance(traits, list) and traits:
            lines.append("Personality traits: " + ", ".join(str(item) for item in traits))
        for key in ["communication_style", "response_depth", "initiative_level", "safety_mode"]:
            value = str(personality.get(key, "")).strip()
            if value:
                lines.append(f"{key.replace('_', ' ').title()}: {value}.")
        do_list = personality.get("do_list", [])
        if isinstance(do_list, list) and do_list:
            lines.append("Always do: " + "; ".join(str(item) for item in do_list))
        dont_list = personality.get("dont_list", [])
        if isinstance(dont_list, list) and dont_list:
            lines.append("Never do: " + "; ".join(str(item) for item in dont_list))

    if isinstance(policies, dict):
        for key, prefix in [
            ("tool_policies", "Tool policy"),
            ("escalation_rules", "Escalation rules"),
            ("memory_hints", "Memory hints"),
            ("success_criteria", "Success criteria"),
        ]:
            value = policies.get(key, [])
            if isinstance(value, list) and value:
                lines.append(f"{prefix}: " + "; ".join(str(item) for item in value))
        template = str(policies.get("response_template", "")).strip()
        if template:
            lines.append(f"Preferred response template: {template}.")
        user_context = str(policies.get("user_context", "")).strip()
        if user_context:
            lines.append(f"Primary user context: {user_context}.")

    return _join_lines(lines).strip()


def compile_persona_system_prompt_resolved(
    *,
    tenant_id: str,
    persona: dict[str, Any],
    org_id: str,
    division_id: str = "",
    team_id: str = "",
) -> str:
    base = compile_persona_system_prompt(persona)
    data = persona.get("data", {}) if isinstance(persona.get("data"), dict) else {}
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    provider_id = str(runtime.get("provider_id", "openai") or "openai").strip().lower()
    resolved = prompt_template_store.resolve_template(
        tenant_id=tenant_id,
        provider_id=provider_id,
        template_kind="system_prompt",
        scopes={"team": team_id, "division": division_id, "org": org_id, "tenant": tenant_id},
    )
    if not resolved:
        return base
    content = str((resolved.get("version", {}) or {}).get("content", "")).strip()
    if not content:
        return base
    context = {
        "persona": {
            "name": persona.get("name", ""),
            "role": persona.get("role", ""),
            "scope": persona.get("scope", "organization"),
            "base_prompt": base,
        }
    }
    rendered = render_template(content, context)
    return rendered or base
