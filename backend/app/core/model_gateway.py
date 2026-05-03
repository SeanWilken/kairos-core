from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.core.async_model_adapters import generate_with_adapter
from app.core.ai_provider import generate_chat_completion
from app.core.model_gateway_policy_store import model_gateway_policy_store


@dataclass
class ModelRequest:
    system_prompt: str
    conversation_messages: list[dict[str, str]]
    model_profile: str = "reasoning-optimized"
    provider_id: str | None = None
    model_id: str | None = None
    tenant_id: str | None = None
    org_id: str | None = None
    timeout_seconds: float = 45.0
    retries: int = 1


@dataclass
class ModelResponse:
    content: str
    provider: str
    model: str
    usage: dict[str, Any]


class ModelGateway:
    async def generate_text(self, request: ModelRequest) -> ModelResponse:
        provider = (request.provider_id or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
        timeout_seconds = request.timeout_seconds
        retries = request.retries
        if request.tenant_id and request.org_id:
            timeout_seconds, retries = model_gateway_policy_store.resolve_runtime_policy(
                tenant_id=request.tenant_id,
                org_id=request.org_id,
                provider_id=("google" if provider == "gemini" else provider),
                model_id=request.model_id,
                default_timeout=request.timeout_seconds,
                default_retries=request.retries,
            )
        result = await generate_with_adapter(
            provider_id=provider,
            system_prompt=request.system_prompt,
            conversation_messages=request.conversation_messages,
            model_profile=request.model_profile,
            model_override=request.model_id,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        return ModelResponse(
            content=result.content,
            provider=result.provider,
            model=result.model,
            usage=result.usage if isinstance(result.usage, dict) else {},
        )

    async def generate_structured(self, request: ModelRequest) -> ModelResponse:
        response = await self.generate_text(request)
        raw = response.content.strip()
        if raw.startswith("```"):
            parts = raw.split("\n")
            if len(parts) >= 3:
                raw = "\n".join(parts[1:-1]).strip()
        json.loads(raw)
        return response

    def generate_text_sync(self, request: ModelRequest) -> ModelResponse:
        result = generate_chat_completion(
            system_prompt=request.system_prompt,
            conversation_messages=request.conversation_messages,
            model_profile=request.model_profile,
            provider_override=request.provider_id,
            model_override=request.model_id,
        )
        return ModelResponse(
            content=result.content,
            provider=result.provider,
            model=result.model,
            usage=result.usage if isinstance(result.usage, dict) else {},
        )


model_gateway = ModelGateway()
