from __future__ import annotations

from typing import Any


PROFILE_PRESETS: list[dict[str, Any]] = [
    {
        "profile_id": "frontend-engineer",
        "label": "Frontend Engineer",
        "description": "Bias toward UI systems, client behavior, and implementation-ready frontend knowledge.",
        "relevancy_focus": {"frontend": 1.0, "product": 0.55, "backend": 0.35},
        "include_node_kinds": ["document", "knowledge_node", "policy", "workflow", "task", "tool"],
        "include_relationship_types": ["implements", "depends_on", "supports", "uses_tool", "related_to"],
        "preferred_tools": ["knowledge_search", "code_generation", "document_create_markdown"],
        "preferred_outputs": ["markdown", "checklist", "code"],
        "voice_defaults": {"tone": "clear", "cadence": "measured"},
    },
    {
        "profile_id": "backend-engineer",
        "label": "Backend Engineer",
        "description": "Bias toward services, contracts, execution traces, runtime behavior, and operational constraints.",
        "relevancy_focus": {"backend": 1.0, "security": 0.6, "devops": 0.55, "compliance": 0.35},
        "include_node_kinds": ["document", "knowledge_node", "service", "workflow", "policy", "tool", "task", "file", "symbol", "project", "glossary_term"],
        "include_relationship_types": ["depends_on", "implements", "governed_by", "supports", "blocks", "similar_to", "duplicate_of", "extracted_from", "should_be_shared"],
        "preferred_tools": ["knowledge_search", "code_generation", "runtime_inspect"],
        "preferred_outputs": ["markdown", "reporting", "code"],
        "voice_defaults": {"tone": "precise", "cadence": "steady"},
    },
    {
        "profile_id": "compliance-reviewer",
        "label": "Compliance Reviewer",
        "description": "Bias toward policy, regulatory, audit, and evidence-linked knowledge.",
        "relevancy_focus": {"compliance": 1.0, "regulatory": 0.95, "security": 0.7, "business": 0.35},
        "include_node_kinds": ["policy", "document", "knowledge_node", "workflow"],
        "include_relationship_types": ["governed_by", "requires_permission", "supports", "contradicts"],
        "preferred_tools": ["knowledge_search", "document_create_markdown"],
        "preferred_outputs": ["reporting", "markdown"],
        "voice_defaults": {"tone": "formal", "cadence": "deliberate"},
    },
    {
        "profile_id": "product-manager",
        "label": "Product Manager",
        "description": "Bias toward product decisions, delivery planning, customer impact, and roadmap context.",
        "relevancy_focus": {"product": 1.0, "business": 0.75, "customer_support": 0.55, "frontend": 0.4},
        "include_node_kinds": ["document", "knowledge_node", "workflow", "task", "roadmap"],
        "include_relationship_types": ["supports", "depends_on", "belongs_to", "related_to"],
        "preferred_tools": ["knowledge_search", "task_create", "document_create_markdown"],
        "preferred_outputs": ["summary", "markdown", "reporting"],
        "voice_defaults": {"tone": "encouraging", "cadence": "balanced"},
    },
    {
        "profile_id": "ai-coding-agent",
        "label": "AI Coding Agent",
        "description": "Bias toward implementation context, prior code patterns, tools, constraints, and execution safety.",
        "relevancy_focus": {"backend": 0.95, "frontend": 0.75, "devops": 0.6, "security": 0.55, "ai": 0.5},
        "include_node_kinds": ["document", "knowledge_node", "tool", "workflow", "policy", "task", "repo", "file", "symbol", "project", "glossary_term"],
        "include_relationship_types": ["implements", "depends_on", "uses_tool", "derived_from", "supports", "similar_to", "duplicate_of", "extracted_from", "should_be_shared"],
        "preferred_tools": ["knowledge_search", "code_generation", "runtime_inspect", "task_create"],
        "preferred_outputs": ["code", "markdown", "checklist"],
        "voice_defaults": {"tone": "neutral", "cadence": "efficient"},
    },
    {
        "profile_id": "help-desk-agent",
        "label": "Help Desk Agent",
        "description": "Bias toward troubleshooting, customer issues, known fixes, SOPs, and escalation paths.",
        "relevancy_focus": {"customer_support": 1.0, "product": 0.55, "backend": 0.45, "security": 0.3},
        "include_node_kinds": ["document", "knowledge_node", "workflow", "policy", "task"],
        "include_relationship_types": ["explains", "supports", "blocks", "escalates_to", "related_to"],
        "preferred_tools": ["knowledge_search", "task_create", "document_create_markdown"],
        "preferred_outputs": ["markdown", "walkthrough", "summary"],
        "voice_defaults": {"tone": "friendly", "cadence": "calm"},
    },
    {
        "profile_id": "generalist",
        "label": "Generalist",
        "description": "Balanced multi-domain retrieval for broad support and exploratory work.",
        "relevancy_focus": {"frontend": 0.55, "backend": 0.55, "product": 0.55, "business": 0.45, "security": 0.35},
        "include_node_kinds": ["document", "knowledge_node", "workflow", "task", "policy", "tool"],
        "include_relationship_types": ["related_to", "supports", "depends_on", "explains"],
        "preferred_tools": ["knowledge_search", "document_create_markdown", "task_create"],
        "preferred_outputs": ["markdown", "summary", "reporting"],
        "voice_defaults": {"tone": "balanced", "cadence": "natural"},
    },
    {
        "profile_id": "knowledge-librarian",
        "label": "Knowledge Librarian",
        "description": "Bias toward indexing, categorization, linking, provenance, and discoverability.",
        "relevancy_focus": {"ai": 0.4, "product": 0.35, "compliance": 0.3, "backend": 0.3},
        "include_node_kinds": ["document", "knowledge_node", "note", "note_collection", "policy", "tool", "file", "symbol", "project", "glossary_term"],
        "include_relationship_types": ["references", "belongs_to", "derived_from", "explains", "related_to", "similar_to", "duplicate_of", "extracted_from", "should_be_shared"],
        "preferred_tools": ["knowledge_search", "document_create_markdown", "relationship_create"],
        "preferred_outputs": ["markdown", "catalog", "summary"],
        "voice_defaults": {"tone": "scholarly", "cadence": "measured"},
    },
    {
        "profile_id": "relations-manager",
        "label": "Relations Manager",
        "description": "Bias toward client communications, commitments, relationship history, and deliverable follow-through.",
        "relevancy_focus": {"business": 0.9, "customer_support": 0.8, "product": 0.5, "frontend": 0.25},
        "include_node_kinds": ["document", "knowledge_node", "task", "workflow", "policy"],
        "include_relationship_types": ["supports", "depends_on", "related_to", "belongs_to"],
        "preferred_tools": ["knowledge_search", "document_create_markdown", "task_create"],
        "preferred_outputs": ["markdown", "summary", "reporting"],
        "voice_defaults": {"tone": "professional", "cadence": "warm"},
    },
    {
        "profile_id": "document-drafter",
        "label": "Document Drafter",
        "description": "Bias toward source material synthesis, structured writing, and document generation workflows.",
        "relevancy_focus": {"product": 0.4, "business": 0.35, "compliance": 0.3, "backend": 0.25},
        "include_node_kinds": ["document", "knowledge_node", "note", "policy", "workflow"],
        "include_relationship_types": ["references", "explains", "supports", "derived_from"],
        "preferred_tools": ["document_create_markdown", "knowledge_search"],
        "preferred_outputs": ["markdown", "reporting", "walkthrough"],
        "voice_defaults": {"tone": "clear", "cadence": "paced"},
    },
    {
        "profile_id": "project-manager",
        "label": "Project Manager",
        "description": "Bias toward delivery coordination, dependencies, planning, and stakeholder visibility.",
        "relevancy_focus": {"product": 0.8, "business": 0.6, "backend": 0.4, "frontend": 0.3},
        "include_node_kinds": ["task", "workflow", "document", "knowledge_node", "policy"],
        "include_relationship_types": ["depends_on", "blocks", "supports", "belongs_to"],
        "preferred_tools": ["task_create", "document_create_markdown", "knowledge_search"],
        "preferred_outputs": ["summary", "checklist", "reporting"],
        "voice_defaults": {"tone": "directive", "cadence": "steady"},
    },
    {
        "profile_id": "scrum-master",
        "label": "Scrum Master",
        "description": "Bias toward blockers, sprint coordination, flow health, and delivery rituals.",
        "relevancy_focus": {"product": 0.7, "backend": 0.45, "frontend": 0.45, "business": 0.35},
        "include_node_kinds": ["task", "workflow", "knowledge_node", "document"],
        "include_relationship_types": ["blocks", "depends_on", "supports", "related_to"],
        "preferred_tools": ["task_create", "knowledge_search", "document_create_markdown"],
        "preferred_outputs": ["checklist", "summary", "walkthrough"],
        "voice_defaults": {"tone": "facilitative", "cadence": "grounded"},
    },
]


PROFILE_ACTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "frontend-engineer": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "code_generation", "priority": 90, "mode_hint": "write"},
            {"tool_id": "document_create_markdown", "priority": 70, "mode_hint": "write", "default_output_profile": "markdown_document"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "backend-engineer": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "runtime_inspect", "priority": 95, "mode_hint": "execute"},
            {"tool_id": "code_generation", "priority": 90, "mode_hint": "write"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "image_generation": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "compliance-reviewer": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "report"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "anthropic"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "product-manager": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "task_create", "priority": 95, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "summary"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "ai-coding-agent": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "runtime_inspect", "priority": 95, "mode_hint": "execute"},
            {"tool_id": "code_generation", "priority": 90, "mode_hint": "write", "default_output_profile": "code"},
            {"tool_id": "task_create", "priority": 60, "mode_hint": "write", "default_output_profile": "task_bundle"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "image_generation": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "help-desk-agent": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "task_create", "priority": 90, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "walkthrough"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "generalist": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 85, "mode_hint": "write", "default_output_profile": "markdown_document"},
            {"tool_id": "task_create", "priority": 70, "mode_hint": "write", "default_output_profile": "task_bundle"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "knowledge-librarian": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "relationship_create", "priority": 90, "mode_hint": "write"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "catalog"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "anthropic"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
    "relations-manager": {
        "preferred_tool_policies": [
            {"tool_id": "knowledge_search", "priority": 100, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 90, "mode_hint": "write", "default_output_profile": "report"},
            {"tool_id": "task_create", "priority": 80, "mode_hint": "write", "default_output_profile": "task_bundle"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "document-drafter": {
        "preferred_tool_policies": [
            {"tool_id": "document_create_markdown", "priority": 100, "mode_hint": "write", "default_output_profile": "markdown_document"},
            {"tool_id": "knowledge_search", "priority": 85, "mode_hint": "read"},
            {"tool_id": "image_generate", "priority": 40, "mode_hint": "write", "default_output_profile": "image_concept"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "anthropic"},
            "document_drafting": {"provider_id": "anthropic"},
            "image_generation": {"provider_id": "google", "model_id": "imagen-3.0-generate-002"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "project-manager": {
        "preferred_tool_policies": [
            {"tool_id": "task_create", "priority": 100, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "document_create_markdown", "priority": 85, "mode_hint": "write", "default_output_profile": "report"},
            {"tool_id": "knowledge_search", "priority": 80, "mode_hint": "read"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "elevenlabs"},
        },
    },
    "scrum-master": {
        "preferred_tool_policies": [
            {"tool_id": "task_create", "priority": 100, "mode_hint": "write", "default_output_profile": "task_bundle"},
            {"tool_id": "knowledge_search", "priority": 85, "mode_hint": "read"},
            {"tool_id": "document_create_markdown", "priority": 80, "mode_hint": "write", "default_output_profile": "walkthrough"},
        ],
        "provider_preferences": {
            "chat": {"provider_id": "openai"},
            "document_drafting": {"provider_id": "anthropic"},
            "text_to_speech": {"provider_id": "piper"},
        },
    },
}


def enrich_profile_preset(item: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(item.get("profile_id", "")).strip()
    defaults = PROFILE_ACTION_DEFAULTS.get(profile_id, {})
    return {**item, **defaults}


def profile_presets_map() -> dict[str, dict[str, Any]]:
    return {
        str(item.get("profile_id", "")).strip(): enrich_profile_preset(item)
        for item in PROFILE_PRESETS
        if str(item.get("profile_id", "")).strip()
    }


def get_profile_preset(profile_id: str | None) -> dict[str, Any] | None:
    normalized = str(profile_id or "").strip()
    if not normalized:
        return None
    return profile_presets_map().get(normalized)


def resolve_provider_preference(
    *,
    profile_id: str | None,
    capability: str,
    provider_id: str | None = None,
    model_id: str | None = None,
) -> tuple[str | None, str | None]:
    explicit_provider = str(provider_id or "").strip() or None
    explicit_model = str(model_id or "").strip() or None
    if explicit_provider or explicit_model:
        return explicit_provider, explicit_model
    profile = get_profile_preset(profile_id)
    if not isinstance(profile, dict):
        return None, None
    preferences = profile.get("provider_preferences", {}) if isinstance(profile.get("provider_preferences"), dict) else {}
    capability_pref = preferences.get(capability, {}) if isinstance(preferences.get(capability), dict) else {}
    resolved_provider = str(capability_pref.get("provider_id", "")).strip() or None
    resolved_model = str(capability_pref.get("model_id", "")).strip() or None
    return resolved_provider, resolved_model
