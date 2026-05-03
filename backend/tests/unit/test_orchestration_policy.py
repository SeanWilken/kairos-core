from app.core.orchestration_policy import resolve_orchestration_mode


def test_resolve_orchestration_mode_keeps_explicit_council() -> None:
    decision = resolve_orchestration_mode(
        requested_mode="council",
        content="Please review this",
        explicit_persona_selected=False,
        room_persona_count=3,
    )
    assert decision.effective_mode == "council"
    assert decision.reason == "explicit_mode"


def test_resolve_orchestration_mode_escalates_on_multi_perspective_prompt() -> None:
    decision = resolve_orchestration_mode(
        requested_mode="single_best",
        content="Compare pros and cons from security and product.",
        explicit_persona_selected=False,
        room_persona_count=2,
    )
    assert decision.effective_mode == "summarized"
    assert decision.reason == "server_preprocessing_escalation"


def test_resolve_orchestration_mode_stays_single_when_persona_explicit() -> None:
    decision = resolve_orchestration_mode(
        requested_mode="single_best",
        content="Compare tradeoff options.",
        explicit_persona_selected=True,
        room_persona_count=3,
    )
    assert decision.effective_mode == "single_best"
    assert decision.reason == "explicit_persona"


def test_resolve_orchestration_mode_respects_auto_escalation_disable() -> None:
    decision = resolve_orchestration_mode(
        requested_mode="single_best",
        content="Compare pros and cons from security and product.",
        explicit_persona_selected=False,
        room_persona_count=3,
        auto_escalation_enabled=False,
    )
    assert decision.effective_mode == "single_best"
    assert decision.reason == "auto_escalation_disabled"
