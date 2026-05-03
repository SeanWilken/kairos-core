from __future__ import annotations

import os
from typing import Any


def _is_configured(provider: str) -> bool:
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    if provider == "google":
        return bool(os.getenv("GEMINI_API_KEY", "").strip())
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if provider == "email":
        return bool(os.getenv("EMAIL_SERVICE_PROVIDER", "").strip())
    return False


def is_provider_configured(provider_id: str) -> bool:
    return _is_configured(str(provider_id or "").strip().lower())


def _models_from_env(key: str, fallback: str) -> list[str]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return [fallback]
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or [fallback]


def get_ai_provider_catalog() -> dict[str, Any]:
    providers = [
        {
            "provider_id": "openai",
            "configured": _is_configured("openai"),
            "models": {
                "chat": _models_from_env("OPENAI_MODELS", os.getenv("LLM_MODEL", "gpt-4o-mini")),
                "image_generation": _models_from_env("OPENAI_IMAGE_MODELS", os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")),
            },
            "default_models": {
                "chat": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                "image_generation": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            },
            "capabilities": ["chat", "image_generation"],
            "tools": [
                {"tool_id": "chat_completion", "capability": "chat"},
                {"tool_id": "image_generation", "capability": "image_generation"},
            ],
        },
        {
            "provider_id": "google",
            "configured": _is_configured("google"),
            "models": {
                "chat": _models_from_env("GEMINI_MODELS", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
                "image_generation": _models_from_env("GEMINI_IMAGE_MODELS", os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")),
                "video_generation": _models_from_env("GEMINI_VIDEO_MODELS", os.getenv("GEMINI_VIDEO_MODEL", "veo-2.0-generate-001")),
            },
            "default_models": {
                "chat": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                "image_generation": os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002"),
                "video_generation": os.getenv("GEMINI_VIDEO_MODEL", "veo-2.0-generate-001"),
            },
            "capabilities": ["chat", "image_generation", "video_generation"],
            "tools": [
                {"tool_id": "chat_completion", "capability": "chat"},
                {"tool_id": "nano_banana", "capability": "image_generation"},
                {"tool_id": "video_generation", "capability": "video_generation"},
            ],
        },
        {
            "provider_id": "anthropic",
            "configured": _is_configured("anthropic"),
            "models": {
                "chat": _models_from_env("ANTHROPIC_MODELS", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")),
            },
            "default_models": {
                "chat": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            },
            "capabilities": ["chat"],
            "tools": [{"tool_id": "chat_completion", "capability": "chat"}],
        },
        {
            "provider_id": "email",
            "configured": _is_configured("email"),
            "models": {},
            "default_models": {},
            "capabilities": ["email_send", "email_read"],
            "tools": [
                {"tool_id": "email_send", "capability": "email_send"},
                {"tool_id": "email_read", "capability": "email_read"},
            ],
        },
    ]

    routing = {
        "chat": os.getenv("TOOL_PROVIDER_CHAT", os.getenv("LLM_PROVIDER", "openai")),
        "image_generation": os.getenv("TOOL_PROVIDER_IMAGE_GENERATION", "google"),
        "video_generation": os.getenv("TOOL_PROVIDER_VIDEO_GENERATION", "google"),
        "email_send": os.getenv("TOOL_PROVIDER_EMAIL_SEND", "email"),
    }
    return {
        "providers": providers,
        "routing": routing,
        "configured_provider_ids": [item["provider_id"] for item in providers if item.get("configured")],
    }


def get_provider_models(*, provider_id: str, capability: str | None = None) -> dict[str, Any] | None:
    catalog = get_ai_provider_catalog()
    for provider in catalog["providers"]:
        if provider.get("provider_id") != provider_id:
            continue
        models = provider.get("models", {}) if isinstance(provider.get("models"), dict) else {}
        if capability:
            return {
                "provider_id": provider_id,
                "capability": capability,
                "models": models.get(capability, []),
                "default_model": (provider.get("default_models", {}) or {}).get(capability),
                "configured": bool(provider.get("configured", False)),
            }
        return {
            "provider_id": provider_id,
            "models": models,
            "default_models": provider.get("default_models", {}),
            "configured": bool(provider.get("configured", False)),
        }
    return None
