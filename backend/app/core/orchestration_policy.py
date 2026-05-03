from __future__ import annotations

import re
from dataclasses import dataclass


COUNCIL_MODES = {"council", "summarized", "threaded", "silent_head"}


@dataclass
class OrchestrationPolicyDecision:
    requested_mode: str
    effective_mode: str
    reason: str
    estimated_calls_min: int


def _has_explicit_mentions(content: str) -> bool:
    return bool(re.search(r"(^|\s)@\w+", content))


def _looks_multi_perspective(content: str) -> bool:
    lowered = content.lower()
    hints = [
        "compare",
        "tradeoff",
        "pros and cons",
        "debate",
        "security and product",
        "architecture and security",
        "multiple perspectives",
        "focus group",
    ]
    return any(token in lowered for token in hints)


def resolve_orchestration_mode(
    *,
    requested_mode: str,
    content: str,
    explicit_persona_selected: bool,
    room_persona_count: int,
    auto_escalation_enabled: bool = True,
) -> OrchestrationPolicyDecision:
    requested = str(requested_mode or "single_best").strip().lower() or "single_best"
    if requested in COUNCIL_MODES:
        return OrchestrationPolicyDecision(
            requested_mode=requested,
            effective_mode=requested,
            reason="explicit_mode",
            estimated_calls_min=2,
        )

    if explicit_persona_selected:
        return OrchestrationPolicyDecision(
            requested_mode=requested,
            effective_mode="single_best",
            reason="explicit_persona",
            estimated_calls_min=1,
        )

    if (
        auto_escalation_enabled
        and room_persona_count >= 2
        and (_has_explicit_mentions(content) or _looks_multi_perspective(content))
    ):
        return OrchestrationPolicyDecision(
            requested_mode=requested,
            effective_mode="summarized",
            reason="server_preprocessing_escalation",
            estimated_calls_min=2,
        )

    if not auto_escalation_enabled:
        return OrchestrationPolicyDecision(
            requested_mode=requested,
            effective_mode="single_best",
            reason="auto_escalation_disabled",
            estimated_calls_min=1,
        )

    return OrchestrationPolicyDecision(
        requested_mode=requested,
        effective_mode="single_best",
        reason="single_fast_path",
        estimated_calls_min=1,
    )
