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
) -> ChatGenerationResult:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = _profile_to_model(model_profile)

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
