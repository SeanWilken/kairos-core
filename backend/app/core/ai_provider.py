from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import request


@dataclass
class ChatGenerationResult:
    content: str
    provider: str
    model: str
    usage: dict[str, Any]


def _openai_endpoint() -> str:
    base = os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1").rstrip("/")
    return f"{base}/chat/completions"


def _gemini_endpoint(model: str, api_key: str) -> str:
    base = os.getenv("GEMINI_API_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    return f"{base}/models/{model}:generateContent?key={api_key}"


def _profile_to_model(profile: str) -> str:
    profile_map = {
        "reasoning-optimized": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "fast": os.getenv("LLM_FAST_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")),
        "balanced": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }
    return profile_map.get(profile, os.getenv("LLM_MODEL", "gpt-4o-mini"))


def _profile_to_gemini_model(profile: str) -> str:
    profile_map = {
        "reasoning-optimized": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        "fast": os.getenv("GEMINI_FAST_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
        "balanced": os.getenv("GEMINI_BALANCED_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    }
    return profile_map.get(profile, os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))


def _simulated_response(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
) -> str:
    last_user_message = ""
    for message in reversed(conversation_messages):
        if message.get("role") == "user":
            last_user_message = str(message.get("content", ""))
            break

    lowered = last_user_message.lower()
    if "return valid json" in lowered and all(
        key in lowered for key in ["introduction", "description", "features", "skills", "resume"]
    ):
        persona_name = "Kairos Persona"
        marker = "you are"
        lowered_system = system_prompt.lower()
        if marker in lowered_system:
            idx = lowered_system.find(marker)
            candidate = system_prompt[idx + len(marker) :].strip().split(".", 1)[0]
            if candidate:
                persona_name = candidate.strip().strip(",")

        payload = {
            "introduction": f"Hello, I am {persona_name}.",
            "description": (
                "I am a persona wrapper configured for structured responses, planning support, "
                "and clear communication."
            ),
            "features": [
                "Structured output",
                "Task decomposition",
                "Context-aware recommendations",
            ],
            "skills": [
                "analysis",
                "planning",
                "communication",
                "documentation",
            ],
            "resume": {
                "title": "AI Persona Assistant",
                "summary": "Supports onboarding, execution planning, and decision support.",
                "strengths": ["Problem framing", "Actionable next steps", "Clear written output"],
                "tooling": ["chat orchestration", "persona policy", "structured JSON responses"],
            },
        }
        return json.dumps(payload)

    return (
        "[simulated-response] OpenAI API key is not configured. "
        "This is a local fallback response for integration testing."
    )


def generate_chat_completion(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> ChatGenerationResult:
    live_mode_enabled = os.getenv("LLM_LIVE_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
    provider = (provider_override or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
    if not live_mode_enabled:
        model = (model_override or (_profile_to_gemini_model(model_profile) if provider == "gemini" else _profile_to_model(model_profile))).strip()
        content = _simulated_response(
            system_prompt=system_prompt,
            conversation_messages=conversation_messages,
        )
        return ChatGenerationResult(
            content=content,
            provider=f"{provider}-simulated",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    if provider == "gemini":
        return _generate_gemini_completion(
            system_prompt=system_prompt,
            conversation_messages=conversation_messages,
            model_profile=model_profile,
            model_override=model_override,
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = (model_override or _profile_to_model(model_profile)).strip()

    if not api_key:
        content = _simulated_response(
            system_prompt=system_prompt,
            conversation_messages=conversation_messages,
        )
        return ChatGenerationResult(
            content=content,
            provider="openai-simulated",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    payload_messages: list[dict[str, str]] = []
    if system_prompt.strip():
        payload_messages.append({"role": "system", "content": system_prompt.strip()})
    payload_messages.extend(conversation_messages)

    payload = {
        "model": model,
        "messages": payload_messages,
        "temperature": 0.4,
    }

    req = request.Request(
        _openai_endpoint(),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as error:
        raise RuntimeError(f"OpenAI provider request failed: {error}") from error

    choices = body.get("choices", []) if isinstance(body, dict) else []
    if not choices:
        raise RuntimeError("OpenAI provider returned no choices.")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI provider returned empty response content.")

    usage = body.get("usage", {}) if isinstance(body, dict) else {}
    return ChatGenerationResult(
        content=content.strip(),
        provider="openai",
        model=model,
        usage=usage if isinstance(usage, dict) else {},
    )


def _generate_gemini_completion(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
    model_override: str | None = None,
) -> ChatGenerationResult:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = (model_override or _profile_to_gemini_model(model_profile)).strip()

    if not api_key:
        content = _simulated_response(
            system_prompt=system_prompt,
            conversation_messages=conversation_messages,
        )
        return ChatGenerationResult(
            content=content,
            provider="gemini-simulated",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    parts = []
    for msg in conversation_messages:
        role = str(msg.get("role", "user"))
        gemini_role = "user" if role == "user" else "model"
        parts.append(
            {
                "role": gemini_role,
                "parts": [{"text": str(msg.get("content", ""))}],
            }
        )

    payload: dict[str, Any] = {
        "contents": parts,
        "generationConfig": {"temperature": 0.4},
    }
    if system_prompt.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_prompt.strip()}]}

    req = request.Request(
        _gemini_endpoint(model, api_key),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as error:
        raise RuntimeError(f"Gemini provider request failed: {error}") from error

    candidates = body.get("candidates", []) if isinstance(body, dict) else []
    if not candidates:
        raise RuntimeError("Gemini provider returned no candidates.")

    content_obj = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
    parts_obj = content_obj.get("parts", []) if isinstance(content_obj, dict) else []
    text_parts = [str(item.get("text", "")) for item in parts_obj if isinstance(item, dict)]
    content = "\n".join(part for part in text_parts if part).strip()
    if not content:
        raise RuntimeError("Gemini provider returned empty response content.")

    usage_metadata = body.get("usageMetadata", {}) if isinstance(body, dict) else {}
    usage = {
        "prompt_tokens": int(usage_metadata.get("promptTokenCount", 0) or 0),
        "completion_tokens": int(usage_metadata.get("candidatesTokenCount", 0) or 0),
        "total_tokens": int(usage_metadata.get("totalTokenCount", 0) or 0),
    }
    return ChatGenerationResult(
        content=content,
        provider="gemini",
        model=model,
        usage=usage,
    )
