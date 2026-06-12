from app.core.chat_contracts import normalize_chat_controls


def test_normalize_chat_controls_soft_warning_for_unknown_field() -> None:
    payload = {
        "content": "hello",
        "mode": "single_best",
        "unknown_field": "value",
    }
    result = normalize_chat_controls(payload)
    assert result["accepted"] is True
    assert result["warnings"]
    assert result["warnings"][0]["reason_code"] == "CHAT_PAYLOAD_UNKNOWN_FIELDS"


def test_normalize_chat_controls_strict_rejects_unknown_field() -> None:
    payload = {
        "content": "hello",
        "strict_validation": True,
        "unknown_field": "value",
    }
    result = normalize_chat_controls(payload)
    assert result["accepted"] is False
    assert result["rejections"]
    assert result["rejections"][0]["reason_code"] == "CHAT_PAYLOAD_UNKNOWN_FIELDS"
