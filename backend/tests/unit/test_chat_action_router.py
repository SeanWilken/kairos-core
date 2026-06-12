from app.core.chat_action_router import resolve_chat_action


def test_resolve_chat_action_routes_persona_mention() -> None:
    decision = resolve_chat_action(
        content="@securityReviewer please review this",
        requested_mode="single_best",
        handle_to_persona_id={"securityreviewer": "persona-1"},
        room_persona_count=2,
    )
    assert decision.action_type == "mention"
    assert decision.resolved_persona_id == "persona-1"
    assert decision.resolved_mode == "single_best"


def test_resolve_chat_action_routes_workflow_focus_to_summarized() -> None:
    decision = resolve_chat_action(
        content="/focus investigate tradeoffs",
        requested_mode="single_best",
        handle_to_persona_id={},
        room_persona_count=3,
    )
    assert decision.action_type == "workflow"
    assert decision.resolved_mode == "summarized"


def test_resolve_chat_action_general_message_defaults() -> None:
    decision = resolve_chat_action(
        content="just a normal message",
        requested_mode="single_best",
        handle_to_persona_id={},
        room_persona_count=1,
    )
    assert decision.action_type == "general"
    assert decision.resolved_mode is None
    assert decision.resolved_persona_id is None


def test_resolve_chat_action_role_call_routes_to_threaded() -> None:
    decision = resolve_chat_action(
        content="role call for participating personas",
        requested_mode="single_best",
        handle_to_persona_id={},
        room_persona_count=2,
    )
    assert decision.action_type == "attendance"
    assert decision.resolved_mode == "threaded"
    assert decision.reason == "persona_roll_call"
