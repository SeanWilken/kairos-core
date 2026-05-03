from __future__ import annotations

from dataclasses import dataclass


def _estimate_tokens(text: str) -> int:
    return max(len((text or "").split()), 0)


@dataclass(slots=True)
class ContextWindowResult:
    messages: list[dict[str, str]]
    raw_token_estimate: int
    compacted_token_estimate: int
    tokens_saved_estimate: int
    compaction_applied: bool


class ContextWindowService:
    def prepare_messages(
        self,
        *,
        messages: list[dict[str, str]],
        level: str,
        disabled: bool,
    ) -> ContextWindowResult:
        raw_tokens = sum(_estimate_tokens(str(item.get("content", ""))) for item in messages)
        if disabled:
            return ContextWindowResult(
                messages=messages,
                raw_token_estimate=raw_tokens,
                compacted_token_estimate=raw_tokens,
                tokens_saved_estimate=0,
                compaction_applied=False,
            )

        normalized = (level or "medium").strip().lower()
        keep_last = 24
        if normalized == "low":
            keep_last = 32
        elif normalized == "high":
            keep_last = 14

        compacted = messages[-keep_last:] if len(messages) > keep_last else messages
        compacted_tokens = sum(_estimate_tokens(str(item.get("content", ""))) for item in compacted)
        return ContextWindowResult(
            messages=compacted,
            raw_token_estimate=raw_tokens,
            compacted_token_estimate=compacted_tokens,
            tokens_saved_estimate=max(raw_tokens - compacted_tokens, 0),
            compaction_applied=len(compacted) != len(messages),
        )


context_window_service = ContextWindowService()
