from __future__ import annotations

from dataclasses import dataclass


def _normalize_handle(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


@dataclass(slots=True)
class ChatActionDecision:
    action_type: str
    resolved_mode: str | None
    resolved_persona_id: str | None
    reason: str


def resolve_chat_action(
    *,
    content: str,
    requested_mode: str,
    handle_to_persona_id: dict[str, str],
    room_persona_count: int,
) -> ChatActionDecision:
    text = str(content or "").strip()
    lowered = text.lower()

    mention_tokens = [token[1:] for token in lowered.replace("\n", " ").split(" ") if token.startswith("@") and len(token) > 1]
    for token in mention_tokens:
        normalized = _normalize_handle(token)
        persona_id = handle_to_persona_id.get(normalized)
        if persona_id:
            return ChatActionDecision(
                action_type="mention",
                resolved_mode="single_best",
                resolved_persona_id=persona_id,
                reason="persona_mention_route",
            )

    if room_persona_count >= 2:
        roll_call_hints = (
            "role call",
            "roll call",
            "who is participating",
            "who is in this chat",
            "check in all personas",
            "all personas check in",
        )
        if any(hint in lowered for hint in roll_call_hints):
            return ChatActionDecision(
                action_type="attendance",
                resolved_mode="threaded",
                resolved_persona_id=None,
                reason="persona_roll_call",
            )

    if lowered.startswith("/focus") or lowered.startswith("/flow"):
        if room_persona_count >= 2:
            return ChatActionDecision(
                action_type="workflow",
                resolved_mode="summarized",
                resolved_persona_id=None,
                reason="workflow_command",
            )
        return ChatActionDecision(
            action_type="workflow",
            resolved_mode="single_best",
            resolved_persona_id=None,
            reason="workflow_command_single_persona",
        )

    if lowered.startswith("/agent") and room_persona_count >= 1:
        return ChatActionDecision(
            action_type="workflow",
            resolved_mode=(requested_mode if requested_mode != "single_best" else "single_best"),
            resolved_persona_id=None,
            reason="agent_command",
        )

    return ChatActionDecision(
        action_type="general",
        resolved_mode=None,
        resolved_persona_id=None,
        reason="general_message",
    )
