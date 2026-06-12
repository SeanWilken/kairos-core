from app.core.persona_prompt import compile_persona_system_prompt


def test_compile_persona_prompt_includes_assigned_tools() -> None:
    persona = {
        "name": "Tool Aware Agent",
        "role": "assistant",
        "scope": "organization",
        "system_prompt": "",
        "data": {
            "assigned_tools": ["nano_banana", "email_send"],
            "operational_policies": {
                "tool_policies": ["enabled_tool:nano_banana", "enabled_tool:email_send"],
            },
        },
    }

    prompt = compile_persona_system_prompt(persona)

    assert "Enabled tools: nano_banana, email_send" in prompt
    assert "requested capability is not in enabled tools" in prompt
