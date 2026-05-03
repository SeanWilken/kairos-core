from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_ENGAGEMENT_MODES = {"manual_only", "command_enabled", "mention_only", "always_on"}
SUPPORTED_COMMAND_PREFIXES = (
    "/ask",
    "/agent",
    "/focus",
    "/flow",
    "/summarize",
    "/handoff",
    "/memory",
    "/tool",
)


@dataclass(slots=True)
class EngagementDecision:
    should_engage: bool
    reason: str


def _normalize_handle(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def evaluate_ai_engagement(
    *,
    content: str,
    mode: str,
    ai_handles: list[str],
) -> EngagementDecision:
    normalized_mode = (mode or "always_on").strip().lower()
    if normalized_mode not in SUPPORTED_ENGAGEMENT_MODES:
        normalized_mode = "always_on"

    text = (content or "").strip()
    if not text:
        return EngagementDecision(should_engage=False, reason="empty_message")

    lowered = text.lower()
    has_command = any(lowered.startswith(prefix) for prefix in SUPPORTED_COMMAND_PREFIXES)

    normalized_text_tokens = {
        _normalize_handle(token[1:])
        for token in lowered.replace("\n", " ").split(" ")
        if token.startswith("@") and len(token) > 1
    }
    known_ai_handles = {_normalize_handle(item) for item in ai_handles if _normalize_handle(item)}
    has_ai_mention = bool(normalized_text_tokens.intersection(known_ai_handles))

    if normalized_mode == "manual_only":
        return EngagementDecision(should_engage=False, reason="manual_only")
    if normalized_mode == "always_on":
        return EngagementDecision(should_engage=True, reason="always_on")
    if normalized_mode == "command_enabled":
        if has_command:
            return EngagementDecision(should_engage=True, reason="command_match")
        if has_ai_mention:
            return EngagementDecision(should_engage=True, reason="ai_mention")
        return EngagementDecision(should_engage=False, reason="command_or_ai_mention_required")
    if has_ai_mention:
        return EngagementDecision(should_engage=True, reason="ai_mention")
    return EngagementDecision(should_engage=False, reason="ai_mention_required")
