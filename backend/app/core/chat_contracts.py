from __future__ import annotations

from typing import Any


ALLOWED_CHAT_TYPES = {"one_to_one", "group"}
ALLOWED_RESPONSE_TYPES = {"conversation", "markdown", "summary", "reporting"}
ALLOWED_MODES = {"single_best", "council", "summarized", "threaded", "silent_head"}
ALLOWED_EFFORT_LEVELS = {"fast", "balanced", "deep"}
MAX_PARTICIPANT_CONTROLS = 16
MAX_EXPLICIT_PERSONA_CALLS = 8
ALLOWED_PARTICIPANT_CONTROL_KEYS = {"response_type", "effort", "runtime_provider_id", "runtime_model_id", "mode"}

ALLOWED_CHAT_KEYS = {
    "action",
    "channel_id",
    "content",
    "persona_id",
    "mode",
    "chat_type",
    "response_type",
    "global_controls",
    "participant_controls",
    "persona_overrides",
    "explicit_persona_calls",
    "auto_execute_tools",
    "strict_validation",
    "idempotency_key",
    "client_message_id",
    "content_blocks",
}

ALLOWED_BLOCK_TYPES = {"text", "markdown", "image", "code", "callout", "table", "report"}


def normalize_chat_controls(payload: dict[str, Any]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []

    strict_validation = bool(payload.get("strict_validation", False))

    unknown_keys = sorted([key for key in payload.keys() if key not in ALLOWED_CHAT_KEYS])
    if unknown_keys:
        issue = {
            "reason_code": "CHAT_PAYLOAD_UNKNOWN_FIELDS",
            "field": "payload",
            "details": {"unknown_fields": unknown_keys},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)

    content = str(payload.get("content", "")).strip()
    if not content:
        rejections.append(
            {
                "reason_code": "CHAT_CONTENT_REQUIRED",
                "field": "content",
                "details": {},
            }
        )

    content_blocks = payload.get("content_blocks", [])
    sanitized_blocks: list[dict[str, Any]] = []
    if content_blocks:
        if not isinstance(content_blocks, list):
            issue = {
                "reason_code": "CHAT_CONTENT_BLOCKS_INVALID",
                "field": "content_blocks",
                "details": {"expected": "array"},
            }
            if strict_validation:
                rejections.append(issue)
            else:
                warnings.append(issue)
        else:
            for index, block in enumerate(content_blocks):
                if not isinstance(block, dict):
                    issue = {
                        "reason_code": "CHAT_CONTENT_BLOCK_ENTRY_INVALID",
                        "field": f"content_blocks[{index}]",
                        "details": {"expected": "object"},
                    }
                    if strict_validation:
                        rejections.append(issue)
                    else:
                        warnings.append(issue)
                    continue
                block_type = str(block.get("type", "")).strip().lower()
                if block_type not in ALLOWED_BLOCK_TYPES:
                    issue = {
                        "reason_code": "CHAT_CONTENT_BLOCK_TYPE_INVALID",
                        "field": f"content_blocks[{index}].type",
                        "details": {"allowed": sorted(ALLOWED_BLOCK_TYPES), "provided": block_type},
                    }
                    if strict_validation:
                        rejections.append(issue)
                    else:
                        warnings.append(issue)
                    continue
                sanitized_blocks.append({**block, "type": block_type})

    chat_type = str(payload.get("chat_type", "")).strip().lower() or "one_to_one"
    if chat_type not in ALLOWED_CHAT_TYPES:
        issue = {
            "reason_code": "CHAT_TYPE_INVALID",
            "field": "chat_type",
            "details": {"allowed": sorted(ALLOWED_CHAT_TYPES), "provided": chat_type},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            chat_type = "one_to_one"

    mode = str(payload.get("mode", "single_best")).strip()
    if mode not in ALLOWED_MODES:
        issue = {
            "reason_code": "CHAT_MODE_INVALID",
            "field": "mode",
            "details": {"allowed": sorted(ALLOWED_MODES), "provided": mode},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            mode = "single_best"

    response_type = str(payload.get("response_type", "conversation")).strip().lower()
    if response_type not in ALLOWED_RESPONSE_TYPES:
        issue = {
            "reason_code": "CHAT_RESPONSE_TYPE_INVALID",
            "field": "response_type",
            "details": {"allowed": sorted(ALLOWED_RESPONSE_TYPES), "provided": response_type},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            response_type = "conversation"

    global_controls = payload.get("global_controls", {})
    if not isinstance(global_controls, dict):
        issue = {
            "reason_code": "CHAT_GLOBAL_CONTROLS_INVALID",
            "field": "global_controls",
            "details": {"expected": "object"},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            global_controls = {}

    participant_controls = payload.get("participant_controls", payload.get("persona_overrides", {}))
    if not isinstance(participant_controls, dict):
        issue = {
            "reason_code": "CHAT_PARTICIPANT_CONTROLS_INVALID",
            "field": "participant_controls",
            "details": {"expected": "object"},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            participant_controls = {}
    sanitized_participant_controls: dict[str, dict[str, Any]] = {}
    if isinstance(participant_controls, dict):
        items = list(participant_controls.items())
        if len(items) > MAX_PARTICIPANT_CONTROLS:
            issue = {
                "reason_code": "CHAT_PARTICIPANT_CONTROLS_LIMIT_EXCEEDED",
                "field": "participant_controls",
                "details": {"max": MAX_PARTICIPANT_CONTROLS, "provided": len(items)},
            }
            if strict_validation:
                rejections.append(issue)
            else:
                warnings.append(issue)
            items = items[:MAX_PARTICIPANT_CONTROLS]

        for persona_id_raw, value in items:
            persona_id = str(persona_id_raw).strip()
            if not persona_id:
                continue
            if not isinstance(value, dict):
                issue = {
                    "reason_code": "CHAT_PARTICIPANT_CONTROL_ENTRY_INVALID",
                    "field": f"participant_controls.{persona_id}",
                    "details": {"expected": "object"},
                }
                if strict_validation:
                    rejections.append(issue)
                else:
                    warnings.append(issue)
                continue
            unknown_entry_keys = sorted([key for key in value.keys() if key not in ALLOWED_PARTICIPANT_CONTROL_KEYS])
            if unknown_entry_keys:
                issue = {
                    "reason_code": "CHAT_PARTICIPANT_CONTROL_UNKNOWN_FIELDS",
                    "field": f"participant_controls.{persona_id}",
                    "details": {"unknown_fields": unknown_entry_keys},
                }
                if strict_validation:
                    rejections.append(issue)
                else:
                    warnings.append(issue)

            entry: dict[str, Any] = {}
            response_type_entry = str(value.get("response_type", "")).strip().lower()
            if response_type_entry:
                if response_type_entry not in ALLOWED_RESPONSE_TYPES:
                    issue = {
                        "reason_code": "CHAT_PARTICIPANT_RESPONSE_TYPE_INVALID",
                        "field": f"participant_controls.{persona_id}.response_type",
                        "details": {"allowed": sorted(ALLOWED_RESPONSE_TYPES), "provided": response_type_entry},
                    }
                    if strict_validation:
                        rejections.append(issue)
                    else:
                        warnings.append(issue)
                else:
                    entry["response_type"] = response_type_entry

            effort_entry = str(value.get("effort", "")).strip().lower()
            if effort_entry:
                if effort_entry not in ALLOWED_EFFORT_LEVELS:
                    issue = {
                        "reason_code": "CHAT_PARTICIPANT_EFFORT_INVALID",
                        "field": f"participant_controls.{persona_id}.effort",
                        "details": {"allowed": sorted(ALLOWED_EFFORT_LEVELS), "provided": effort_entry},
                    }
                    if strict_validation:
                        rejections.append(issue)
                    else:
                        warnings.append(issue)
                else:
                    entry["effort"] = effort_entry

            mode_entry = str(value.get("mode", "")).strip()
            if mode_entry:
                if mode_entry not in ALLOWED_MODES:
                    issue = {
                        "reason_code": "CHAT_PARTICIPANT_MODE_INVALID",
                        "field": f"participant_controls.{persona_id}.mode",
                        "details": {"allowed": sorted(ALLOWED_MODES), "provided": mode_entry},
                    }
                    if strict_validation:
                        rejections.append(issue)
                    else:
                        warnings.append(issue)
                else:
                    entry["mode"] = mode_entry

            runtime_provider_id = str(value.get("runtime_provider_id", "")).strip().lower()
            if runtime_provider_id:
                entry["runtime_provider_id"] = runtime_provider_id
            runtime_model_id = str(value.get("runtime_model_id", "")).strip()
            if runtime_model_id:
                entry["runtime_model_id"] = runtime_model_id

            sanitized_participant_controls[persona_id] = entry

    explicit_persona_calls = payload.get("explicit_persona_calls", [])
    if not isinstance(explicit_persona_calls, list):
        issue = {
            "reason_code": "CHAT_EXPLICIT_PERSONA_CALLS_INVALID",
            "field": "explicit_persona_calls",
            "details": {"expected": "array"},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            explicit_persona_calls = []
    explicit_persona_calls = [str(item).strip() for item in explicit_persona_calls if str(item).strip()]
    if len(explicit_persona_calls) > MAX_EXPLICIT_PERSONA_CALLS:
        issue = {
            "reason_code": "CHAT_EXPLICIT_PERSONA_CALLS_LIMIT_EXCEEDED",
            "field": "explicit_persona_calls",
            "details": {"max": MAX_EXPLICIT_PERSONA_CALLS, "provided": len(explicit_persona_calls)},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            explicit_persona_calls = explicit_persona_calls[:MAX_EXPLICIT_PERSONA_CALLS]

    if chat_type == "one_to_one" and explicit_persona_calls:
        issue = {
            "reason_code": "CHAT_EXPLICIT_PERSONA_CALLS_ONE_TO_ONE_IGNORED",
            "field": "explicit_persona_calls",
            "details": {},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            explicit_persona_calls = []

    auto_execute_tools = bool(payload.get("auto_execute_tools", True))

    effort = str(global_controls.get("effort", "")).strip().lower()
    if effort and effort not in ALLOWED_EFFORT_LEVELS:
        issue = {
            "reason_code": "CHAT_EFFORT_INVALID",
            "field": "global_controls.effort",
            "details": {"allowed": sorted(ALLOWED_EFFORT_LEVELS), "provided": effort},
        }
        if strict_validation:
            rejections.append(issue)
        else:
            warnings.append(issue)
            global_controls = {**global_controls}
            global_controls.pop("effort", None)

    accepted = len(rejections) == 0
    return {
        "accepted": accepted,
        "strict_validation": strict_validation,
        "normalized": {
            "content": content,
            "chat_type": chat_type,
            "mode": mode,
            "response_type": response_type,
            "global_controls": global_controls,
            "participant_controls": sanitized_participant_controls,
            "explicit_persona_calls": explicit_persona_calls,
            "auto_execute_tools": auto_execute_tools,
            "persona_id": (
                str(payload.get("persona_id")).strip()
                if payload.get("persona_id") is not None and str(payload.get("persona_id")).strip()
                else None
            ),
            "content_blocks": sanitized_blocks,
        },
        "warnings": warnings,
        "rejections": rejections,
        "validation_summary": {
            "warning_count": len(warnings),
            "rejection_count": len(rejections),
        },
    }
