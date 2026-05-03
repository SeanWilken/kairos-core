from __future__ import annotations

from typing import Any


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flatten(value, full))
        elif isinstance(value, list):
            out[full] = ", ".join(str(item) for item in value)
        elif value is None:
            out[full] = ""
        else:
            out[full] = str(value)
    return out


def render_template(content: str, context: dict[str, Any]) -> str:
    rendered = str(content or "")
    for key, value in _flatten(context).items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered.strip()
