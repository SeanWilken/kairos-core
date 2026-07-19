from __future__ import annotations

import os
import shutil
from typing import Any


def get_tool_catalog() -> dict[str, Any]:
    tools = [
        {
            "tool_id": "speech_to_text",
            "label": "Speech To Text",
            "category": "speech_audio",
            "description": "Transcribe uploaded audio into text.",
            "risk_level": "low",
            "approval_mode": "none",
            "side_effect_level": "read",
            "wrapper_command": "myai speech transcribe",
            "capabilities": ["speech_to_text", "transcription"],
            "implementations": [
                {"implementation_id": "whisper_cpp", "kind": "host_cli", "binary_name": "whisper-cli", "provider_id": None, "default": True},
                {"implementation_id": "command", "kind": "wrapper_only", "binary_name": "", "provider_id": None, "default": False},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["manual", "installer"]},
            "profile_affinity": ["help-desk-agent", "generalist", "knowledge-librarian"],
            "provider_preferences": {},
            "status": "supported",
        },
        {
            "tool_id": "text_to_speech",
            "label": "Text To Speech",
            "category": "speech_audio",
            "description": "Synthesize speech from arbitrary text.",
            "risk_level": "low",
            "approval_mode": "none",
            "side_effect_level": "read",
            "wrapper_command": "myai speech synth",
            "capabilities": ["text_to_speech", "voice_generation"],
            "implementations": [
                {"implementation_id": "piper", "kind": "host_cli", "binary_name": "piper", "provider_id": None, "default": True},
                {"implementation_id": "elevenlabs", "kind": "api_provider", "binary_name": "", "provider_id": "elevenlabs", "default": False},
                {"implementation_id": "command", "kind": "wrapper_only", "binary_name": "", "provider_id": None, "default": False},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["manual", "installer"]},
            "profile_affinity": ["generalist", "relations-manager", "document-drafter"],
            "provider_preferences": {},
            "status": "supported",
        },
        {
            "tool_id": "image_generate",
            "label": "Image Generation",
            "category": "image_generation",
            "description": "Generate images from prompts through configured provider/model routes.",
            "risk_level": "medium",
            "approval_mode": "none",
            "side_effect_level": "write",
            "wrapper_command": "myai image generate",
            "capabilities": ["image_generation"],
            "implementations": [
                {"implementation_id": "nano_banana", "kind": "api_provider", "binary_name": "", "provider_id": "google", "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["provider"]},
            "profile_affinity": ["document-drafter", "project-manager", "generalist"],
            "provider_preferences": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "status": "supported",
        },
        {
            "tool_id": "email_send",
            "label": "Email Send",
            "category": "email_calendar",
            "description": "Send outbound email through configured transport.",
            "risk_level": "medium",
            "approval_mode": "single",
            "side_effect_level": "write",
            "wrapper_command": "myai email send",
            "capabilities": ["email_send"],
            "implementations": [
                {"implementation_id": "email_transport", "kind": "embedded_runtime", "binary_name": "", "provider_id": "email", "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["provider"]},
            "profile_affinity": ["relations-manager", "help-desk-agent"],
            "provider_preferences": {"provider_id": "email"},
            "status": "supported",
        },
        {
            "tool_id": "document_create_markdown",
            "label": "Document Create Markdown",
            "category": "document_processing",
            "description": "Generate markdown-oriented document content for notes, walkthroughs, and drafts.",
            "risk_level": "low",
            "approval_mode": "none",
            "side_effect_level": "write",
            "wrapper_command": "myai doc draft",
            "capabilities": ["document_drafting", "markdown_output"],
            "implementations": [
                {"implementation_id": "llm_markdown_draft", "kind": "api_provider", "binary_name": "", "provider_id": None, "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["provider"]},
            "profile_affinity": ["document-drafter", "knowledge-librarian", "project-manager"],
            "provider_preferences": {"provider_id": "anthropic"},
            "status": "planned",
        },
        {
            "tool_id": "pdf_generate",
            "label": "PDF Generate",
            "category": "document_processing",
            "description": "Render markdown or report content into a PDF artifact.",
            "risk_level": "low",
            "approval_mode": "none",
            "side_effect_level": "write",
            "wrapper_command": "myai doc pdf",
            "capabilities": ["pdf_generation", "document_rendering"],
            "implementations": [
                {"implementation_id": "command", "kind": "host_cli", "binary_name": "", "provider_id": None, "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["manual", "installer"]},
            "profile_affinity": ["document-drafter", "relations-manager", "project-manager", "scrum-master", "help-desk-agent"],
            "provider_preferences": {},
            "status": "planned",
        },
        {
            "tool_id": "task_create",
            "label": "Task Create",
            "category": "workflow_support",
            "description": "Create task records and associated workflow artifacts.",
            "risk_level": "low",
            "approval_mode": "none",
            "side_effect_level": "write",
            "wrapper_command": "myai task create",
            "capabilities": ["task_create"],
            "implementations": [
                {"implementation_id": "core_task_api", "kind": "embedded_runtime", "binary_name": "", "provider_id": None, "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["builtin"]},
            "profile_affinity": ["project-manager", "scrum-master", "help-desk-agent"],
            "provider_preferences": {},
            "status": "supported",
        },
        {
            "tool_id": "workflow_create",
            "label": "Workflow Create",
            "category": "workflow_support",
            "description": "Generate a structured workflow or implementation scaffold from a prompt.",
            "risk_level": "low",
            "approval_mode": "none",
            "side_effect_level": "write",
            "wrapper_command": "myai workflow create",
            "capabilities": ["workflow_scaffold", "markdown_output"],
            "implementations": [
                {"implementation_id": "llm_workflow_scaffold", "kind": "api_provider", "binary_name": "", "provider_id": None, "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["provider"]},
            "profile_affinity": ["project-manager", "scrum-master", "generalist"],
            "provider_preferences": {"provider_id": "anthropic"},
            "status": "planned",
        },
        {
            "tool_id": "relationship_create",
            "label": "Relationship Create",
            "category": "workflow_support",
            "description": "Create explicit knowledge graph relationships between entities.",
            "risk_level": "medium",
            "approval_mode": "single",
            "side_effect_level": "write",
            "wrapper_command": "myai relationship create",
            "capabilities": ["graph_relationship_write"],
            "implementations": [
                {"implementation_id": "knowledge_relationship_api", "kind": "embedded_runtime", "binary_name": "", "provider_id": None, "default": True},
            ],
            "host_requirements": {"os": ["windows", "linux", "macos"], "architectures": ["amd64", "arm64"], "install_modes": ["builtin"]},
            "profile_affinity": ["knowledge-librarian", "generalist"],
            "provider_preferences": {},
            "status": "planned",
        },
    ]
    return {"tools": tools}


def get_tool_runtime_registry() -> dict[str, Any]:
    entries = [
        _runtime_entry_for_whisper_cpp(),
        _runtime_entry_for_piper(),
        _runtime_entry_for_elevenlabs(),
        _runtime_entry_for_pdf_render(),
        _runtime_entry_for_imagemagick(),
        _runtime_entry_for_git(),
    ]
    return {"items": entries}


def _resolve_binary(explicit_path: str, fallback_name: str) -> tuple[str, bool]:
    explicit = str(explicit_path or "").strip()
    if explicit:
        return explicit, os.path.exists(explicit)
    if fallback_name:
        resolved = shutil.which(fallback_name) or ""
        return resolved, bool(resolved)
    return "", False


def _runtime_entry(tool_id: str, implementation_id: str, binary_path: str, installed: bool, version: str = "", config: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "implementation_id": implementation_id,
        "installed": installed,
        "binary_path": binary_path,
        "validated": installed,
        "version": version,
        "config": config or {},
    }


def _runtime_entry_for_whisper_cpp() -> dict[str, Any]:
    path, installed = _resolve_binary(os.getenv("MYAI_STT_WHISPER_CPP_BIN", ""), "whisper-cli")
    return _runtime_entry(
        "speech_to_text",
        "whisper_cpp",
        path,
        installed and bool(os.getenv("MYAI_STT_WHISPER_CPP_MODEL", "").strip()),
        config={"model_path": os.getenv("MYAI_STT_WHISPER_CPP_MODEL", ""), "language": os.getenv("MYAI_STT_LANGUAGE", "en")},
    )


def _runtime_entry_for_piper() -> dict[str, Any]:
    path, installed = _resolve_binary(os.getenv("MYAI_TTS_PIPER_BIN", ""), "piper")
    return _runtime_entry(
        "text_to_speech",
        "piper",
        path,
        installed and bool(os.getenv("MYAI_TTS_PIPER_MODEL", "").strip()),
        config={"model_path": os.getenv("MYAI_TTS_PIPER_MODEL", ""), "voice": os.getenv("MYAI_TTS_VOICE", "default")},
    )


def _runtime_entry_for_elevenlabs() -> dict[str, Any]:
    installed = bool(os.getenv("MYAI_TTS_ELEVENLABS_API_KEY", "").strip()) and bool(os.getenv("MYAI_TTS_ELEVENLABS_VOICE_ID", "").strip())
    return _runtime_entry(
        "text_to_speech",
        "elevenlabs",
        "remote-api",
        installed,
        config={
            "voice": os.getenv("MYAI_TTS_ELEVENLABS_VOICE_ID", ""),
            "model": os.getenv("MYAI_TTS_ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
            "base_url": os.getenv("MYAI_TTS_ELEVENLABS_BASE_URL", "https://api.elevenlabs.io"),
        },
    )


def _runtime_entry_for_imagemagick() -> dict[str, Any]:
    path, installed = _resolve_binary(os.getenv("MYAI_IMAGEMAGICK_BIN", ""), "magick")
    return _runtime_entry("image_process", "imagemagick", path, installed)


def _runtime_entry_for_git() -> dict[str, Any]:
    path, installed = _resolve_binary(os.getenv("MYAI_GIT_BIN", ""), "git")
    return _runtime_entry("git_status", "git", path, installed)


def _runtime_entry_for_pdf_render() -> dict[str, Any]:
    template = os.getenv("MYAI_PDF_COMMAND_TEMPLATE", "").strip()
    installed = bool(template)
    return _runtime_entry(
        "pdf_generate",
        "command",
        "command-template",
        installed,
        config={"command_template": template},
    )
