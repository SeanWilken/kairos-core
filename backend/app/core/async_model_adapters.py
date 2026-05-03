from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class AsyncAdapterResult:
    content: str
    provider: str
    model: str
    usage: dict[str, Any]


def _provider_timeout(provider_id: str, fallback: float) -> float:
    key = f"MODEL_GATEWAY_TIMEOUT_SECONDS_{provider_id.upper()}"
    raw = os.getenv(key, "").strip() or os.getenv("MODEL_GATEWAY_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return fallback
    try:
        value = float(raw)
        return value if value > 0 else fallback
    except ValueError:
        return fallback


def _provider_retries(provider_id: str, fallback: int) -> int:
    key = f"MODEL_GATEWAY_RETRIES_{provider_id.upper()}"
    raw = os.getenv(key, "").strip() or os.getenv("MODEL_GATEWAY_RETRIES", "").strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
        return value if value >= 0 else fallback
    except ValueError:
        return fallback


def _openai_model(profile: str) -> str:
    profile_map = {
        "reasoning-optimized": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "fast": os.getenv("LLM_FAST_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")),
        "balanced": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }
    return profile_map.get(profile, os.getenv("LLM_MODEL", "gpt-4o-mini"))


def _google_model(profile: str) -> str:
    profile_map = {
        "reasoning-optimized": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        "fast": os.getenv("GEMINI_FAST_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
        "balanced": os.getenv("GEMINI_BALANCED_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    }
    return profile_map.get(profile, os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))


def _anthropic_model(profile: str) -> str:
    profile_map = {
        "reasoning-optimized": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        "fast": os.getenv("ANTHROPIC_FAST_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")),
        "balanced": os.getenv("ANTHROPIC_BALANCED_MODEL", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")),
    }
    return profile_map.get(profile, os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))


def _simulated_content(conversation_messages: list[dict[str, str]]) -> str:
    last_user_message = ""
    for message in reversed(conversation_messages):
        if message.get("role") == "user":
            last_user_message = str(message.get("content", ""))
            break
    return f"[simulated-response] {last_user_message or 'No user content provided.'}"


async def generate_openai(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
    model_override: str | None,
    timeout_seconds: float,
) -> AsyncAdapterResult:
    model = (model_override or _openai_model(model_profile)).strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return AsyncAdapterResult(
            content=_simulated_content(conversation_messages),
            provider="openai-simulated",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    base = os.getenv("LLM_ENDPOINT", "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    payload_messages: list[dict[str, str]] = []
    if system_prompt.strip():
        payload_messages.append({"role": "system", "content": system_prompt.strip()})
    payload_messages.extend(conversation_messages)
    payload = {"model": model, "messages": payload_messages, "temperature": 0.4}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI provider request failed: {resp.status_code}")
    body = resp.json()
    choices = body.get("choices", []) if isinstance(body, dict) else []
    if not choices:
        raise RuntimeError("OpenAI provider returned no choices.")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = message.get("content", "") if isinstance(message, dict) else ""
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI provider returned empty response content.")
    usage = body.get("usage", {}) if isinstance(body, dict) else {}
    return AsyncAdapterResult(
        content=content.strip(),
        provider="openai",
        model=model,
        usage=usage if isinstance(usage, dict) else {},
    )


async def generate_google(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
    model_override: str | None,
    timeout_seconds: float,
) -> AsyncAdapterResult:
    model = (model_override or _google_model(model_profile)).strip()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return AsyncAdapterResult(
            content=_simulated_content(conversation_messages),
            provider="gemini-simulated",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    base = os.getenv("GEMINI_API_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    url = f"{base}/models/{model}:generateContent?key={api_key}"
    parts = []
    for msg in conversation_messages:
        role = str(msg.get("role", "user"))
        parts.append(
            {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": str(msg.get("content", ""))}],
            }
        )
    payload: dict[str, Any] = {"contents": parts, "generationConfig": {"temperature": 0.4}}
    if system_prompt.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_prompt.strip()}]}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini provider request failed: {resp.status_code}")
    body = resp.json()
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
    return AsyncAdapterResult(content=content, provider="gemini", model=model, usage=usage)


async def generate_anthropic(
    *,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
    model_override: str | None,
    timeout_seconds: float,
) -> AsyncAdapterResult:
    model = (model_override or _anthropic_model(model_profile)).strip()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return AsyncAdapterResult(
            content=_simulated_content(conversation_messages),
            provider="anthropic-simulated",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    url = os.getenv("ANTHROPIC_API_ENDPOINT", "https://api.anthropic.com/v1/messages").strip()
    payload_messages = [
        {"role": str(item.get("role", "user")), "content": str(item.get("content", ""))}
        for item in conversation_messages
    ]
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 1024,
        "messages": payload_messages,
    }
    if system_prompt.strip():
        payload["system"] = system_prompt.strip()

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        resp = await client.post(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Anthropic provider request failed: {resp.status_code}")
    body = resp.json()
    blocks = body.get("content", []) if isinstance(body, dict) else []
    parts = [str(item.get("text", "")) for item in blocks if isinstance(item, dict)]
    content = "\n".join(part for part in parts if part).strip()
    if not content:
        raise RuntimeError("Anthropic provider returned empty response content.")
    usage_obj = body.get("usage", {}) if isinstance(body, dict) else {}
    usage = {
        "prompt_tokens": int(usage_obj.get("input_tokens", 0) or 0),
        "completion_tokens": int(usage_obj.get("output_tokens", 0) or 0),
        "total_tokens": int((usage_obj.get("input_tokens", 0) or 0) + (usage_obj.get("output_tokens", 0) or 0)),
    }
    return AsyncAdapterResult(content=content, provider="anthropic", model=model, usage=usage)


async def generate_with_adapter(
    *,
    provider_id: str,
    system_prompt: str,
    conversation_messages: list[dict[str, str]],
    model_profile: str,
    model_override: str | None,
    timeout_seconds: float,
    retries: int,
) -> AsyncAdapterResult:
    provider = (provider_id or "openai").strip().lower()
    if provider == "gemini":
        provider = "google"
    timeout = _provider_timeout(provider, timeout_seconds)
    retry_count = _provider_retries(provider, retries)
    last_error: Exception | None = None

    for _ in range(retry_count + 1):
        try:
            if provider == "google":
                return await generate_google(
                    system_prompt=system_prompt,
                    conversation_messages=conversation_messages,
                    model_profile=model_profile,
                    model_override=model_override,
                    timeout_seconds=timeout,
                )
            if provider == "anthropic":
                return await generate_anthropic(
                    system_prompt=system_prompt,
                    conversation_messages=conversation_messages,
                    model_profile=model_profile,
                    model_override=model_override,
                    timeout_seconds=timeout,
                )
            return await generate_openai(
                system_prompt=system_prompt,
                conversation_messages=conversation_messages,
                model_profile=model_profile,
                model_override=model_override,
                timeout_seconds=timeout,
            )
        except Exception as error:
            last_error = error
    raise RuntimeError(f"{provider} adapter request failed after retries: {last_error}")
