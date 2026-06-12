from __future__ import annotations

from typing import Any

from app.core.prompt_template_renderer import render_template
from app.core.prompt_template_store import prompt_template_store


def resolve_rendered_prompt_template(
    *,
    tenant_id: str,
    provider_id: str,
    template_kind: str,
    scopes: dict[str, str],
    context: dict[str, Any],
) -> str:
    resolved = prompt_template_store.resolve_template(
        tenant_id=tenant_id,
        provider_id=str(provider_id or "openai").strip().lower(),
        template_kind=str(template_kind or "").strip(),
        scopes=scopes,
    )
    if not resolved:
        return ""
    content = str((resolved.get("version", {}) or {}).get("content", "")).strip()
    if not content:
        return ""
    return render_template(content, context)
