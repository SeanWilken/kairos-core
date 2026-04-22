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


def _profile_to_model(profile: str) -> str:
    profile_map = {
        "reasoning-optimized": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "fast": os.getenv("LLM_FAST_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")),
        "balanced": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }
    return profile_map.get(profile, os.getenv("LLM_MODEL", "gpt-4o-mini"))


def generate_chat_completion(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
) -> ChatGenerationResult:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = _profile_to_model(model_profile)

    if not api_key:
        content = (
            "[simulated-response] OpenAI API key is not configured. "
            "This is a local fallback response for integration testing."
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
