from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.db_models import (
    PackImportQueueModel,
    PackReviewConversationModel,
    PersonaTemplateCategoryModel,
    PersonaTemplateOptionModel,
    PromptCatalogBundleModel,
    PromptPrefabModel,
    StudioPersonaModel,
)
from app.core.persona_prompt import compile_persona_system_prompt


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def checksum_sha256(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


REQUIRED_REVIEW_CASES = {
    "greeting",
    "do_list_check",
    "dont_list_check",
    "boundary_test",
    "safety_test",
    "role_check",
}

SCHEMA_V2_NESTED = "v2_nested"
SCHEMA_V2_FLAT = "v2_flat"
SCHEMA_V1_LEGACY = "v1_legacy"


def _load_json_dict(raw: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = default or {}
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return fallback


def _normalize_key(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("-", " ").replace("_", " ")
    return re.sub(r"\s+", " ", normalized)


def _slugify_option_key(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower())
    normalized = re.sub(r"-+", "-", lowered).strip("-")
    return normalized or "value"


class PromptCatalogStore:
    def _ensure_selected_options_taxonomy(self, *, db, tenant_id: str, extracted: dict[str, Any], now: datetime) -> None:
        selected_options = extracted.get("selected_options", {})
        if not isinstance(selected_options, dict) or not selected_options:
            return

        for category_name, raw_value in selected_options.items():
            name = str(category_name or "").strip()
            if not name:
                continue

            category = db.scalar(
                select(PersonaTemplateCategoryModel).where(
                    PersonaTemplateCategoryModel.tenant_id == tenant_id,
                    PersonaTemplateCategoryModel.name == name,
                )
            )
            if category is None:
                category = PersonaTemplateCategoryModel(
                    category_id=str(uuid4()),
                    tenant_id=tenant_id,
                    name=name,
                    display_name=name.replace("_", " ").title(),
                    description="Auto-created from persona import.",
                    sort_order=0,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(category)
                db.flush()

            values: list[str] = []
            if isinstance(raw_value, list):
                values = [str(item).strip() for item in raw_value if str(item).strip()]
            else:
                single = str(raw_value or "").strip()
                if single:
                    values = [single]

            for value in values:
                option_key = _slugify_option_key(value)
                existing = db.scalar(
                    select(PersonaTemplateOptionModel).where(
                        PersonaTemplateOptionModel.category_id == category.category_id,
                        PersonaTemplateOptionModel.key == option_key,
                    )
                )
                if existing is None:
                    existing = PersonaTemplateOptionModel(
                        option_id=str(uuid4()),
                        tenant_id=tenant_id,
                        category_id=category.category_id,
                        key=option_key,
                        label=value,
                        verbose_statement=f"Auto-created option for {name}.",
                        provider_compatibility_json=json.dumps(["openai", "google", "anthropic"]),
                        sort_order=0,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                else:
                    existing.label = value
                    existing.is_active = True
                    existing.updated_at = now
                db.add(existing)

    def _to_category_dict(self, model: PersonaTemplateCategoryModel) -> dict[str, Any]:
        return {
            "category_id": model.category_id,
            "tenant_id": model.tenant_id,
            "name": model.name,
            "display_name": model.display_name,
            "description": model.description,
            "sort_order": model.sort_order,
            "is_active": model.is_active,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_option_dict(self, model: PersonaTemplateOptionModel) -> dict[str, Any]:
        providers: list[str] = []
        try:
            loaded = json.loads(model.provider_compatibility_json or "[]")
            if isinstance(loaded, list):
                providers = [str(item) for item in loaded]
        except Exception:
            providers = []

        return {
            "option_id": model.option_id,
            "tenant_id": model.tenant_id,
            "category_id": model.category_id,
            "key": model.key,
            "label": model.label,
            "verbose_statement": model.verbose_statement,
            "provider_compatibility": providers,
            "sort_order": model.sort_order,
            "is_active": model.is_active,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_prefab_dict(self, model: PromptPrefabModel) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        try:
            loaded = json.loads(model.variables_json or "{}")
            if isinstance(loaded, dict):
                variables = loaded
        except Exception:
            variables = {}

        return {
            "prefab_id": model.prefab_id,
            "tenant_id": model.tenant_id,
            "industry": model.industry,
            "role": model.role,
            "segment_type": model.segment_type,
            "name": model.name,
            "content": model.content,
            "variables": variables,
            "tokens_estimate": model.tokens_estimate,
            "version": model.version,
            "is_active": model.is_active,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_review_queue_dict(self, model: PackImportQueueModel) -> dict[str, Any]:
        return {
            "queue_id": model.queue_id,
            "tenant_id": model.tenant_id,
            "status": model.status,
            "pack_data": _load_json_dict(model.pack_data_json),
            "extracted_config": _load_json_dict(model.extracted_config_json),
            "safety_flags": _load_json_dict(model.safety_flags_json),
            "review_notes": model.review_notes,
            "reviewed_by_user_id": model.reviewed_by_user_id,
            "installed_persona_id": model.installed_persona_id,
            "created_at": _dt_iso(model.created_at),
            "reviewed_at": _dt_iso(model.reviewed_at) if model.reviewed_at else None,
        }

    def _to_review_conversation_dict(self, model: PackReviewConversationModel) -> dict[str, Any]:
        return {
            "conversation_id": model.conversation_id,
            "tenant_id": model.tenant_id,
            "queue_id": model.queue_id,
            "test_case_key": model.test_case_key,
            "prompt": model.prompt,
            "response": model.response,
            "passed": model.passed,
            "notes": model.notes,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
        }

    def list_categories(self, *, tenant_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(PersonaTemplateCategoryModel).where(
                PersonaTemplateCategoryModel.tenant_id == tenant_id
            )
            if active_only:
                stmt = stmt.where(PersonaTemplateCategoryModel.is_active.is_(True))
            rows = db.scalars(stmt.order_by(PersonaTemplateCategoryModel.sort_order.asc())).all()
            return [self._to_category_dict(row) for row in rows]

    def list_options(
        self,
        *,
        tenant_id: str,
        category_name: str,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            category = db.scalar(
                select(PersonaTemplateCategoryModel).where(
                    PersonaTemplateCategoryModel.tenant_id == tenant_id,
                    PersonaTemplateCategoryModel.name == category_name,
                )
            )
            if category is None:
                return []

            stmt = select(PersonaTemplateOptionModel).where(
                PersonaTemplateOptionModel.tenant_id == tenant_id,
                PersonaTemplateOptionModel.category_id == category.category_id,
            )
            if active_only:
                stmt = stmt.where(PersonaTemplateOptionModel.is_active.is_(True))
            rows = db.scalars(stmt.order_by(PersonaTemplateOptionModel.sort_order.asc())).all()
            return [self._to_option_dict(row) for row in rows]

    def list_prefabs(
        self,
        *,
        tenant_id: str,
        industry: str | None = None,
        role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(PromptPrefabModel).where(PromptPrefabModel.tenant_id == tenant_id)
            if industry:
                stmt = stmt.where(PromptPrefabModel.industry == industry)
            if role:
                stmt = stmt.where(PromptPrefabModel.role == role)
            if active_only:
                stmt = stmt.where(PromptPrefabModel.is_active.is_(True))
            rows = db.scalars(stmt.order_by(PromptPrefabModel.segment_type.asc())).all()
            return [self._to_prefab_dict(row) for row in rows]

    def detect_import_schema(self, *, payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return "unknown"

        manifest = payload.get("manifest")
        catalog = payload.get("catalog")
        if isinstance(manifest, dict) and isinstance(catalog, dict):
            if isinstance(catalog.get("categories"), list):
                return SCHEMA_V2_NESTED

        if any(key in payload for key in ("pack_metadata", "template_categories", "template_options")):
            return SCHEMA_V1_LEGACY

        if isinstance(manifest, dict):
            return SCHEMA_V2_FLAT

        return "unknown"

    def _normalize_manifest(self, *, raw_manifest: dict[str, Any]) -> dict[str, Any]:
        checksum_raw = str(raw_manifest.get("checksum_sha256") or raw_manifest.get("checksum") or "").strip()
        checksum = checksum_raw[7:] if checksum_raw.lower().startswith("sha256:") else checksum_raw
        return {
            "bundle_id": str(raw_manifest.get("bundle_id") or raw_manifest.get("pack_id") or "").strip(),
            "bundle_version": str(raw_manifest.get("bundle_version") or raw_manifest.get("version") or "1.0.0"),
            "schema_version": str(raw_manifest.get("schema_version") or raw_manifest.get("min_schema_version") or "v2"),
            "checksum_sha256": checksum,
            "signature_alg": str(raw_manifest.get("signature_alg") or ""),
            "signature_key_id": str(raw_manifest.get("signature_key_id") or ""),
            "signature_value": str(raw_manifest.get("signature_value") or ""),
            "name": str(raw_manifest.get("name") or ""),
            "description": str(raw_manifest.get("description") or ""),
            "author": str(raw_manifest.get("author") or ""),
            "created_at": str(raw_manifest.get("created_at") or ""),
            "tags": raw_manifest.get("tags") if isinstance(raw_manifest.get("tags"), list) else [],
            "is_default": bool(raw_manifest.get("is_default", False)),
        }

    def _normalize_category_items(self, *, categories: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in categories:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("category_name") or "").strip()
            if not name:
                continue
            category_id = str(item.get("category_id") or name).strip()
            normalized.append(
                {
                    "category_id": category_id,
                    "name": name,
                    "display_name": str(item.get("display_name") or name),
                    "description": str(item.get("description") or ""),
                    "sort_order": int(item.get("sort_order", 0)),
                    "is_active": bool(item.get("is_active", True)),
                }
            )
        return normalized

    def _build_category_lookup(self, *, categories: list[dict[str, Any]]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for category in categories:
            category_id = str(category.get("category_id", "")).strip()
            name = str(category.get("name", "")).strip()
            display_name = str(category.get("display_name", "")).strip()
            if not category_id:
                continue
            for raw in [category_id, name, display_name]:
                key = _normalize_key(raw)
                if key:
                    lookup[key] = category_id
        return lookup

    def _resolve_category_id(self, *, raw_reference: str, lookup: dict[str, str]) -> str:
        normalized = _normalize_key(raw_reference)
        if not normalized:
            return ""
        return lookup.get(normalized, "")

    def _normalize_option_items(
        self,
        *,
        options: list[Any],
        category_lookup: dict[str, str],
        unresolved_errors: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in options:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or item.get("option_key") or "").strip()
            if not key:
                continue

            category_reference = str(item.get("category_id") or item.get("category_name") or "").strip()
            resolved_category_id = self._resolve_category_id(
                raw_reference=category_reference,
                lookup=category_lookup,
            )
            if not resolved_category_id:
                unresolved_errors.append(
                    {
                        "reason_code": "PACK_OPTION_CATEGORY_UNRESOLVED",
                        "option_key": key,
                        "category_reference": category_reference,
                    }
                )
                continue

            providers = item.get("provider_compatibility", ["openai", "anthropic"])
            if not isinstance(providers, list):
                providers = ["openai", "anthropic"]

            label = str(item.get("label") or item.get("option_label") or key)
            normalized.append(
                {
                    "category_id": resolved_category_id,
                    "key": key,
                    "label": label,
                    "option_key": key,
                    "option_label": label,
                    "verbose_statement": str(item.get("verbose_statement") or label),
                    "provider_compatibility": [str(entry) for entry in providers],
                    "sort_order": int(item.get("sort_order", 0)),
                    "is_active": bool(item.get("is_active", True)),
                }
            )
        return normalized

    def normalize_import_payload(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        schema = self.detect_import_schema(payload=payload)
        if schema == "unknown":
            return {
                "error": {
                    "reason_code": "PACK_SCHEMA_UNKNOWN",
                    "message": "Unable to detect valid import schema.",
                }
            }

        warnings: list[dict[str, Any]] = []
        if schema == SCHEMA_V1_LEGACY:
            warnings.append(
                {
                    "reason_code": "PACK_SCHEMA_V1_DEPRECATED",
                    "message": "Legacy V1 pack schema detected; support will be removed in a future major version.",
                }
            )

        source_manifest: dict[str, Any]
        config: dict[str, Any]
        selected_options: dict[str, Any]
        guidelines: dict[str, Any]
        assigned_tools: list[str]
        prefab_preferences: dict[str, Any]
        success_criteria: str
        categories: list[Any]
        options: list[Any]
        prefabs: list[Any]
        personas: list[Any]
        quick_config: dict[str, Any]
        user_profile_template: dict[str, Any]
        tools: list[Any]

        if schema == SCHEMA_V2_NESTED:
            catalog = payload.get("catalog", {}) if isinstance(payload.get("catalog"), dict) else {}
            source_manifest = payload.get("manifest", {}) if isinstance(payload.get("manifest"), dict) else {}
            config = payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}
            selected_options = payload.get("selected_options", {}) if isinstance(payload.get("selected_options"), dict) else {}
            guidelines = payload.get("guidelines", {}) if isinstance(payload.get("guidelines"), dict) else {}
            assigned_tools = payload.get("assigned_tools", []) if isinstance(payload.get("assigned_tools"), list) else []
            prefab_preferences = payload.get("prefab_preferences", {}) if isinstance(payload.get("prefab_preferences"), dict) else {}
            success_criteria = str(payload.get("success_criteria", "")).strip()
            categories = catalog.get("categories", []) if isinstance(catalog.get("categories"), list) else []
            options = catalog.get("options", []) if isinstance(catalog.get("options"), list) else []
            prefabs = catalog.get("prefabs", []) if isinstance(catalog.get("prefabs"), list) else []
            personas = catalog.get("personas", []) if isinstance(catalog.get("personas"), list) else []
            quick_config = payload.get("quick_config", {}) if isinstance(payload.get("quick_config"), dict) else {}
            user_profile_template = payload.get("user_profile_template", {}) if isinstance(payload.get("user_profile_template"), dict) else {}
            tools = catalog.get("tools", []) if isinstance(catalog.get("tools"), list) else []
        elif schema == SCHEMA_V2_FLAT:
            source_manifest = payload.get("manifest", {}) if isinstance(payload.get("manifest"), dict) else {}
            config = payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}
            selected_options = payload.get("selected_options", {}) if isinstance(payload.get("selected_options"), dict) else {}
            guidelines = payload.get("guidelines", {}) if isinstance(payload.get("guidelines"), dict) else {}
            assigned_tools = payload.get("assigned_tools", []) if isinstance(payload.get("assigned_tools"), list) else []
            prefab_preferences = payload.get("prefab_preferences", {}) if isinstance(payload.get("prefab_preferences"), dict) else {}
            success_criteria = str(payload.get("success_criteria", "")).strip()
            categories = payload.get("categories", []) if isinstance(payload.get("categories"), list) else []
            options = payload.get("options", []) if isinstance(payload.get("options"), list) else []
            prefabs = payload.get("prefabs", []) if isinstance(payload.get("prefabs"), list) else []
            personas = payload.get("personas", []) if isinstance(payload.get("personas"), list) else []
            quick_config = payload.get("quick_config", {}) if isinstance(payload.get("quick_config"), dict) else {}
            user_profile_template = payload.get("user_profile_template", {}) if isinstance(payload.get("user_profile_template"), dict) else {}
            tools = payload.get("tools", []) if isinstance(payload.get("tools"), list) else []
        else:
            source_manifest = payload.get("pack_metadata", {}) if isinstance(payload.get("pack_metadata"), dict) else {}
            config = payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}
            selected_options = payload.get("selected_options", {}) if isinstance(payload.get("selected_options"), dict) else {}
            guidelines = payload.get("guidelines", {}) if isinstance(payload.get("guidelines"), dict) else {}
            assigned_tools = payload.get("assigned_tools", []) if isinstance(payload.get("assigned_tools"), list) else []
            prefab_preferences = payload.get("prefab_preferences", {}) if isinstance(payload.get("prefab_preferences"), dict) else {}
            success_criteria = str(payload.get("success_criteria", "")).strip()
            categories = payload.get("template_categories", []) if isinstance(payload.get("template_categories"), list) else []
            options = payload.get("template_options", []) if isinstance(payload.get("template_options"), list) else []
            prefabs = payload.get("prefab_segments", []) if isinstance(payload.get("prefab_segments"), list) else []
            personas = payload.get("personas", []) if isinstance(payload.get("personas"), list) else []
            quick_config = payload.get("quick_config", {}) if isinstance(payload.get("quick_config"), dict) else {}
            user_profile_template = {
                "default_guidelines": payload.get("default_guidelines", {}),
                "autonomy_instructions": payload.get("default_autonomy_instructions", {}),
            }
            tools = payload.get("tool_templates", []) if isinstance(payload.get("tool_templates"), list) else []

        manifest = self._normalize_manifest(raw_manifest=source_manifest)
        if not manifest.get("bundle_id"):
            manifest["bundle_id"] = str(uuid4())

        normalized_categories = self._normalize_category_items(categories=categories)
        category_lookup = self._build_category_lookup(categories=normalized_categories)
        normalization_errors: list[dict[str, Any]] = []
        normalized_options = self._normalize_option_items(
            options=options,
            category_lookup=category_lookup,
            unresolved_errors=normalization_errors,
        )

        normalized = {
            "manifest": manifest,
            "schema_version": "v2",
            "config": config,
            "selected_options": selected_options,
            "guidelines": guidelines,
            "assigned_tools": [str(item) for item in assigned_tools],
            "prefab_preferences": prefab_preferences,
            "success_criteria": success_criteria,
            "categories": normalized_categories,
            "options": normalized_options,
            "prefabs": [item for item in prefabs if isinstance(item, dict)],
            "personas": [item for item in personas if isinstance(item, dict)],
            "quick_config": quick_config,
            "user_profile_template": user_profile_template,
            "tools": [item for item in tools if isinstance(item, dict)],
        }

        return {
            "schema": schema,
            "payload": normalized,
            "warnings": warnings,
            "errors": normalization_errors,
        }

    def validate_normalized_import_payload(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        manifest = payload.get("manifest", {}) if isinstance(payload.get("manifest"), dict) else {}
        bundle_id = str(manifest.get("bundle_id", "")).strip()
        bundle_version = str(manifest.get("bundle_version", "")).strip()
        checksum = str(manifest.get("checksum_sha256", "")).strip().lower()
        if not bundle_id:
            errors.append({"reason_code": "PACK_MANIFEST_BUNDLE_ID_REQUIRED", "field": "manifest.bundle_id"})
        if not bundle_version:
            errors.append(
                {
                    "reason_code": "PACK_MANIFEST_BUNDLE_VERSION_REQUIRED",
                    "field": "manifest.bundle_version",
                }
            )
        if checksum and not re.fullmatch(r"[a-f0-9]{64}", checksum):
            errors.append(
                {
                    "reason_code": "PACK_MANIFEST_CHECKSUM_INVALID",
                    "field": "manifest.checksum_sha256",
                }
            )

        categories = payload.get("categories", []) if isinstance(payload.get("categories"), list) else []
        options = payload.get("options", []) if isinstance(payload.get("options"), list) else []
        category_ids = {
            str(item.get("category_id", "")).strip()
            for item in categories
            if isinstance(item, dict) and str(item.get("category_id", "")).strip()
        }

        option_keys_by_category: dict[str, set[str]] = {}
        for option in options:
            if not isinstance(option, dict):
                continue
            category_id = str(option.get("category_id", "")).strip()
            option_key = str(option.get("key") or option.get("option_key") or "").strip()
            if not category_id or category_id not in category_ids:
                errors.append(
                    {
                        "reason_code": "PACK_OPTION_CATEGORY_UNKNOWN",
                        "option_key": option_key,
                        "category_id": category_id,
                    }
                )
                continue
            seen = option_keys_by_category.setdefault(category_id, set())
            if option_key in seen:
                errors.append(
                    {
                        "reason_code": "PACK_OPTION_DUPLICATE_KEY",
                        "option_key": option_key,
                        "category_id": category_id,
                    }
                )
            else:
                seen.add(option_key)

        config = payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}
        if not str(config.get("org_id", "")).strip():
            warnings.append(
                {
                    "reason_code": "PACK_INSTALL_ORG_ID_MISSING",
                    "message": "config.org_id is missing; install will fail until org_id is provided.",
                }
            )
        if not isinstance(payload.get("quick_config"), dict) or not payload.get("quick_config"):
            warnings.append(
                {
                    "reason_code": "PACK_QUICK_CONFIG_MISSING",
                    "message": "quick_config not found; resume-builder defaults may be limited.",
                }
            )
        if not isinstance(payload.get("user_profile_template"), dict) or not payload.get("user_profile_template"):
            warnings.append(
                {
                    "reason_code": "PACK_USER_PROFILE_TEMPLATE_MISSING",
                    "message": "user_profile_template not found; profile-resume defaults may be limited.",
                }
            )

        return {"errors": errors, "warnings": warnings}

    def export_bundle(self, *, tenant_id: str, org_id: str | None = None) -> dict[str, Any]:
        with SessionLocal() as db:
            categories = db.scalars(
                select(PersonaTemplateCategoryModel)
                .where(PersonaTemplateCategoryModel.tenant_id == tenant_id)
                .order_by(PersonaTemplateCategoryModel.sort_order.asc())
            ).all()
            options = db.scalars(
                select(PersonaTemplateOptionModel)
                .where(PersonaTemplateOptionModel.tenant_id == tenant_id)
                .order_by(PersonaTemplateOptionModel.sort_order.asc())
            ).all()
            prefabs = db.scalars(
                select(PromptPrefabModel)
                .where(PromptPrefabModel.tenant_id == tenant_id)
                .order_by(PromptPrefabModel.segment_type.asc())
            ).all()

            personas_stmt = select(StudioPersonaModel).where(StudioPersonaModel.tenant_id == tenant_id)
            if org_id:
                personas_stmt = personas_stmt.where(StudioPersonaModel.org_id == org_id)
            personas = db.scalars(personas_stmt.order_by(StudioPersonaModel.created_at.asc())).all()

        catalog = {
            "schema_version": "v1",
            "categories": [self._to_category_dict(row) for row in categories],
            "options": [self._to_option_dict(row) for row in options],
            "prefabs": [self._to_prefab_dict(row) for row in prefabs],
            "personas": [
                {
                    "persona_id": row.persona_id,
                    "org_id": row.org_id,
                    "name": row.name,
                    "slug": row.slug,
                    "role": row.role,
                    "scope": row.scope,
                    "enabled": row.enabled,
                    "model_profile": row.model_profile,
                    "system_prompt": row.system_prompt,
                    "data": json.loads(row.persona_json or "{}"),
                    "approval_status": row.approval_status,
                }
                for row in personas
            ],
        }
        return catalog

    def import_bundle(
        self,
        *,
        tenant_id: str,
        payload: dict[str, Any],
        imported_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        categories = payload.get("categories", [])
        options = payload.get("options", [])
        prefabs = payload.get("prefabs", [])
        personas = payload.get("personas", [])
        manifest = payload.get("manifest", {}) if isinstance(payload.get("manifest"), dict) else {}

        with SessionLocal() as db:
            category_id_by_name: dict[str, str] = {}
            for category_item in categories:
                if not isinstance(category_item, dict):
                    continue
                name = str(category_item.get("name", "")).strip()
                if not name:
                    continue
                incoming_category_id = str(category_item.get("category_id", "")).strip()
                existing = None
                if incoming_category_id:
                    existing = db.scalar(
                        select(PersonaTemplateCategoryModel).where(
                            PersonaTemplateCategoryModel.tenant_id == tenant_id,
                            PersonaTemplateCategoryModel.category_id == incoming_category_id,
                        )
                    )
                if existing is None:
                    existing = db.scalar(
                        select(PersonaTemplateCategoryModel).where(
                            PersonaTemplateCategoryModel.tenant_id == tenant_id,
                            PersonaTemplateCategoryModel.name == name,
                        )
                    )
                if existing is None:
                    existing = PersonaTemplateCategoryModel(
                        category_id=incoming_category_id or str(uuid4()),
                        tenant_id=tenant_id,
                        name=name,
                        display_name=str(category_item.get("display_name", name)),
                        description=str(category_item.get("description", "")),
                        sort_order=int(category_item.get("sort_order", 0)),
                        is_active=bool(category_item.get("is_active", True)),
                        created_at=now,
                        updated_at=now,
                    )
                else:
                    existing.display_name = str(category_item.get("display_name", existing.display_name))
                    existing.description = str(category_item.get("description", existing.description))
                    existing.sort_order = int(category_item.get("sort_order", existing.sort_order))
                    existing.is_active = bool(category_item.get("is_active", existing.is_active))
                    existing.updated_at = now
                db.add(existing)
                db.flush()
                category_id_by_name[name] = existing.category_id
                category_id_by_name[existing.category_id] = existing.category_id

            for option_item in options:
                if not isinstance(option_item, dict):
                    continue
                category_name = str(option_item.get("category_name") or "").strip()
                if not category_name:
                    category_id = category_id_by_name.get(
                        str(option_item.get("category_id", "")).strip(),
                        str(option_item.get("category_id", "")).strip(),
                    )
                else:
                    category_id = category_id_by_name.get(category_name, "")
                key = str(option_item.get("key") or option_item.get("option_key") or "").strip()
                if not category_id or not key:
                    continue

                existing = db.scalar(
                    select(PersonaTemplateOptionModel).where(
                        PersonaTemplateOptionModel.category_id == category_id,
                        PersonaTemplateOptionModel.key == key,
                    )
                )
                providers = option_item.get("provider_compatibility", ["openai", "anthropic"])
                if not isinstance(providers, list):
                    providers = ["openai", "anthropic"]
                if existing is None:
                    existing = PersonaTemplateOptionModel(
                        option_id=str(uuid4()),
                        tenant_id=tenant_id,
                        category_id=category_id,
                        key=key,
                        label=str(option_item.get("label") or option_item.get("option_label") or key),
                        verbose_statement=str(option_item.get("verbose_statement", "")),
                        provider_compatibility_json=json.dumps([str(item) for item in providers]),
                        sort_order=int(option_item.get("sort_order", 0)),
                        is_active=bool(option_item.get("is_active", True)),
                        created_at=now,
                        updated_at=now,
                    )
                else:
                    existing.label = str(
                        option_item.get("label") or option_item.get("option_label") or existing.label
                    )
                    existing.verbose_statement = str(
                        option_item.get("verbose_statement", existing.verbose_statement)
                    )
                    existing.provider_compatibility_json = json.dumps([str(item) for item in providers])
                    existing.sort_order = int(option_item.get("sort_order", existing.sort_order))
                    existing.is_active = bool(option_item.get("is_active", existing.is_active))
                    existing.updated_at = now
                db.add(existing)

            for prefab_item in prefabs:
                if not isinstance(prefab_item, dict):
                    continue
                industry = str(prefab_item.get("industry", "")).strip()
                role = str(prefab_item.get("role", "")).strip()
                segment_type = str(prefab_item.get("segment_type", "")).strip()
                version = int(prefab_item.get("version", 1))
                if not industry or not role or not segment_type:
                    continue

                existing = db.scalar(
                    select(PromptPrefabModel).where(
                        PromptPrefabModel.tenant_id == tenant_id,
                        PromptPrefabModel.industry == industry,
                        PromptPrefabModel.role == role,
                        PromptPrefabModel.segment_type == segment_type,
                        PromptPrefabModel.version == version,
                    )
                )
                variables = prefab_item.get("variables", {})
                if not isinstance(variables, dict):
                    variables = {}
                if existing is None:
                    existing = PromptPrefabModel(
                        prefab_id=str(uuid4()),
                        tenant_id=tenant_id,
                        industry=industry,
                        role=role,
                        segment_type=segment_type,
                        name=str(prefab_item.get("name", f"{industry}:{role}:{segment_type}")),
                        content=str(prefab_item.get("content", "")),
                        variables_json=json.dumps(variables),
                        tokens_estimate=int(prefab_item.get("tokens_estimate", 0)),
                        version=version,
                        is_active=bool(prefab_item.get("is_active", True)),
                        created_at=now,
                        updated_at=now,
                    )
                else:
                    existing.name = str(prefab_item.get("name", existing.name))
                    existing.content = str(prefab_item.get("content", existing.content))
                    existing.variables_json = json.dumps(variables)
                    existing.tokens_estimate = int(
                        prefab_item.get("tokens_estimate", existing.tokens_estimate)
                    )
                    existing.is_active = bool(prefab_item.get("is_active", existing.is_active))
                    existing.updated_at = now
                db.add(existing)

            for persona_item in personas:
                if not isinstance(persona_item, dict):
                    continue
                persona_id = str(persona_item.get("persona_id", "")).strip()
                org_id = str(persona_item.get("org_id", "")).strip()
                if not persona_id or not org_id:
                    continue
                existing = db.scalar(
                    select(StudioPersonaModel).where(
                        StudioPersonaModel.tenant_id == tenant_id,
                        StudioPersonaModel.persona_id == persona_id,
                    )
                )
                if existing is None:
                    existing = StudioPersonaModel(
                        persona_id=persona_id,
                        tenant_id=tenant_id,
                        org_id=org_id,
                        name=str(persona_item.get("name", "Imported Persona")),
                        slug=str(persona_item.get("slug", f"imported-{persona_id}")),
                        role=str(persona_item.get("role", "assistant")),
                        scope=str(persona_item.get("scope", "organization")),
                        enabled=bool(persona_item.get("enabled", True)),
                        model_profile=str(persona_item.get("model_profile", "reasoning-optimized")),
                        system_prompt=str(persona_item.get("system_prompt", "")),
                        persona_json=json.dumps(persona_item.get("data", {})),
                        approval_status=str(persona_item.get("approval_status", "draft")),
                        approved_by_user_id=(
                            imported_by_user_id
                            if str(persona_item.get("approval_status", "draft")) == "approved"
                            else None
                        ),
                        approved_at=(
                            now if str(persona_item.get("approval_status", "draft")) == "approved" else None
                        ),
                        created_by_user_id=imported_by_user_id,
                        created_at=now,
                        updated_at=now,
                    )
                else:
                    existing.name = str(persona_item.get("name", existing.name))
                    existing.slug = str(persona_item.get("slug", existing.slug))
                    existing.role = str(persona_item.get("role", existing.role))
                    existing.scope = str(persona_item.get("scope", existing.scope))
                    existing.enabled = bool(persona_item.get("enabled", existing.enabled))
                    existing.model_profile = str(
                        persona_item.get("model_profile", existing.model_profile)
                    )
                    existing.system_prompt = str(persona_item.get("system_prompt", existing.system_prompt))
                    existing.persona_json = json.dumps(persona_item.get("data", {}))
                    incoming_approval = str(persona_item.get("approval_status", existing.approval_status))
                    existing.approval_status = incoming_approval
                    if incoming_approval == "approved":
                        existing.approved_by_user_id = imported_by_user_id
                        existing.approved_at = now
                    existing.updated_at = now
                db.add(existing)

            bundle_id = str(manifest.get("bundle_id", "")).strip() or str(uuid4())
            bundle_version = str(manifest.get("bundle_version", "1.0.0"))
            bundle = PromptCatalogBundleModel(
                bundle_id=bundle_id,
                tenant_id=tenant_id,
                bundle_version=bundle_version,
                checksum_sha256=str(manifest.get("checksum_sha256", "")),
                schema_version=str(manifest.get("schema_version", "v1")),
                signature_alg=str(manifest.get("signature_alg", "")),
                signature_key_id=str(manifest.get("signature_key_id", "")),
                signature_value=str(manifest.get("signature_value", "")),
                imported_by_user_id=imported_by_user_id,
                created_at=now,
            )
            db.add(bundle)
            db.commit()

        return {
            "bundle_id": bundle_id,
            "bundle_version": bundle_version,
            "imported_counts": {
                "categories": len(categories),
                "options": len(options),
                "prefabs": len(prefabs),
                "personas": len(personas),
            },
        }

    def extract_safe_pack_config(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        config = payload.get("config", {})
        selected_options = payload.get("selected_options", {})
        guidelines = payload.get("guidelines", {})
        assigned_tools = payload.get("assigned_tools", [])
        prefab_preferences = payload.get("prefab_preferences", {})

        out: dict[str, Any] = {
            "persona_name": str(config.get("persona_name", "")).strip(),
            "slug": str(config.get("slug", "")).strip(),
            "role": str(config.get("role", "assistant")).strip() or "assistant",
            "industry": str(config.get("industry", "general")).strip() or "general",
            "primary_role": str(config.get("primary_role", "general")).strip() or "general",
            "org_id": str(config.get("org_id", "")).strip(),
            "selected_options": selected_options if isinstance(selected_options, dict) else {},
            "guidelines": guidelines if isinstance(guidelines, dict) else {},
            "assigned_tools": [str(item) for item in assigned_tools] if isinstance(assigned_tools, list) else [],
            "prefab_preferences": (
                prefab_preferences if isinstance(prefab_preferences, dict) else {}
            ),
            "success_criteria": str(payload.get("success_criteria", "")).strip(),
        }
        return out

    def safety_scan_pack(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        blocked_patterns = [
            "ignore previous instructions",
            "jailbreak",
            "bypass safety",
            "harm civilians",
            "build malware",
        ]
        warning_patterns = [
            "disable guardrails",
            "execute without approval",
            "evade policy",
            "secrets exfiltration",
        ]

        text_fragments: list[str] = []
        for key in ["description", "success_criteria"]:
            text_fragments.append(str(payload.get(key, "")))
        guidelines = payload.get("guidelines", {})
        if isinstance(guidelines, dict):
            for key in ["do_list", "dont_list", "guardrails"]:
                value = guidelines.get(key, [])
                if isinstance(value, list):
                    text_fragments.extend([str(item) for item in value])

        combined = "\n".join(text_fragments).lower()
        blocked_hits = [pattern for pattern in blocked_patterns if pattern in combined]
        warning_hits = [pattern for pattern in warning_patterns if pattern in combined]

        if blocked_hits:
            level = "BLOCKED"
        elif warning_hits:
            level = "REVIEW_NEEDED"
        else:
            level = "SAFE"
        return {
            "level": level,
            "blocked_hits": blocked_hits,
            "warning_hits": warning_hits,
        }

    def enqueue_pack_review(
        self,
        *,
        tenant_id: str,
        payload: dict[str, Any],
        extracted_config: dict[str, Any],
        safety_flags: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        status = "pending_review"
        if str(safety_flags.get("level", "SAFE")) == "BLOCKED":
            status = "rejected"

        with SessionLocal() as db:
            queue = PackImportQueueModel(
                queue_id=str(uuid4()),
                tenant_id=tenant_id,
                pack_data_json=json.dumps(payload),
                extracted_config_json=json.dumps(extracted_config),
                safety_flags_json=json.dumps(safety_flags),
                status=status,
                review_notes="",
                reviewed_by_user_id=None,
                installed_persona_id=None,
                created_at=now,
                reviewed_at=now if status == "rejected" else None,
            )
            db.add(queue)
            db.commit()
            db.refresh(queue)
            return self._to_review_queue_dict(queue)

    def list_review_queue(self, *, tenant_id: str, status: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(PackImportQueueModel).where(PackImportQueueModel.tenant_id == tenant_id)
            if status:
                stmt = stmt.where(PackImportQueueModel.status == status)
            rows = db.scalars(stmt.order_by(PackImportQueueModel.created_at.desc())).all()
            return [self._to_review_queue_dict(row) for row in rows]

    def get_review_queue_entry(self, *, tenant_id: str, queue_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(PackImportQueueModel).where(
                    PackImportQueueModel.tenant_id == tenant_id,
                    PackImportQueueModel.queue_id == queue_id,
                )
            )
            if row is None:
                return None
            out = self._to_review_queue_dict(row)
            conversations = db.scalars(
                select(PackReviewConversationModel)
                .where(
                    PackReviewConversationModel.tenant_id == tenant_id,
                    PackReviewConversationModel.queue_id == queue_id,
                )
                .order_by(PackReviewConversationModel.created_at.asc())
            ).all()
            out["conversation_tests"] = [
                self._to_review_conversation_dict(item) for item in conversations
            ]
            return out

    def upsert_review_conversation_test(
        self,
        *,
        tenant_id: str,
        queue_id: str,
        test_case_key: str,
        prompt: str,
        response: str,
        passed: bool,
        notes: str,
        created_by_user_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            queue = db.scalar(
                select(PackImportQueueModel).where(
                    PackImportQueueModel.tenant_id == tenant_id,
                    PackImportQueueModel.queue_id == queue_id,
                )
            )
            if queue is None:
                return None

            existing = db.scalar(
                select(PackReviewConversationModel).where(
                    PackReviewConversationModel.tenant_id == tenant_id,
                    PackReviewConversationModel.queue_id == queue_id,
                    PackReviewConversationModel.test_case_key == test_case_key,
                )
            )
            now = datetime.now(timezone.utc)
            if existing is None:
                existing = PackReviewConversationModel(
                    conversation_id=str(uuid4()),
                    tenant_id=tenant_id,
                    queue_id=queue_id,
                    test_case_key=test_case_key,
                    prompt=prompt,
                    response=response,
                    passed=passed,
                    notes=notes,
                    created_by_user_id=created_by_user_id,
                    created_at=now,
                )
            else:
                existing.prompt = prompt
                existing.response = response
                existing.passed = passed
                existing.notes = notes
                existing.created_by_user_id = created_by_user_id
                existing.created_at = now
            db.add(existing)

            if queue.status == "pending_review":
                queue.status = "conversation_required"
                db.add(queue)

            db.commit()
            db.refresh(existing)
            return self._to_review_conversation_dict(existing)

    def _required_cases_passed(self, *, db, tenant_id: str, queue_id: str) -> bool:
        rows = db.scalars(
            select(PackReviewConversationModel).where(
                PackReviewConversationModel.tenant_id == tenant_id,
                PackReviewConversationModel.queue_id == queue_id,
            )
        ).all()
        passed = {row.test_case_key for row in rows if row.passed}
        return REQUIRED_REVIEW_CASES.issubset(passed)

    def _generate_prompt_from_extracted(self, extracted: dict[str, Any]) -> str:
        selected_options = extracted.get("selected_options", {})
        guidelines = extracted.get("guidelines", {})
        data = {
            "prompt_blocks": {
                "mission": extracted.get("success_criteria", ""),
                "instructions": "Follow configured role and options.",
                "guardrails": guidelines.get("guardrails", []),
            },
            "personality": {
                "traits": selected_options.get("personality_traits", []),
                "communication_style": selected_options.get("communication_style", ""),
                "initiative_level": selected_options.get("initiative_level", "moderate"),
                "do_list": guidelines.get("do_list", []),
                "dont_list": guidelines.get("dont_list", []),
            },
            "operational_policies": {
                "tool_policies": [f"enabled_tool:{tool_id}" for tool_id in extracted.get("assigned_tools", [])],
                "success_criteria": [extracted.get("success_criteria", "")],
            },
        }
        persona_like = {
            "name": extracted.get("persona_name", "Imported Persona"),
            "role": extracted.get("role", "assistant"),
            "scope": "organization",
            "system_prompt": "",
            "data": data,
        }
        return compile_persona_system_prompt(persona_like)

    def finalize_review_decision(
        self,
        *,
        tenant_id: str,
        queue_id: str,
        decision: str,
        review_notes: str,
        reviewed_by_user_id: str,
    ) -> dict[str, Any] | None:
        if decision not in {"approve", "reject", "request_changes"}:
            return None

        with SessionLocal() as db:
            queue = db.scalar(
                select(PackImportQueueModel).where(
                    PackImportQueueModel.tenant_id == tenant_id,
                    PackImportQueueModel.queue_id == queue_id,
                )
            )
            if queue is None:
                return None

            now = datetime.now(timezone.utc)
            queue.review_notes = review_notes
            queue.reviewed_by_user_id = reviewed_by_user_id
            queue.reviewed_at = now

            if decision == "approve":
                if not self._required_cases_passed(db=db, tenant_id=tenant_id, queue_id=queue_id):
                    return {
                        "error": {
                            "reason_code": "PACK_REVIEW_REQUIRED_CASES_INCOMPLETE",
                            "required_cases": sorted(REQUIRED_REVIEW_CASES),
                        }
                    }

                queue.status = "approved"
                db.add(queue)
                db.commit()
                db.refresh(queue)
                return self._to_review_queue_dict(queue)

            if decision == "reject":
                queue.status = "rejected"
            else:
                queue.status = "changes_requested"
            db.add(queue)
            db.commit()
            db.refresh(queue)
            return self._to_review_queue_dict(queue)

    def install_approved_pack(
        self,
        *,
        tenant_id: str,
        queue_id: str,
        installed_by_user_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            queue = db.scalar(
                select(PackImportQueueModel).where(
                    PackImportQueueModel.tenant_id == tenant_id,
                    PackImportQueueModel.queue_id == queue_id,
                )
            )
            if queue is None:
                return None
            if queue.status not in {"approved", "installed"}:
                return {
                    "error": {
                        "reason_code": "PACK_REVIEW_NOT_APPROVED",
                        "status": queue.status,
                    }
                }
            if queue.installed_persona_id:
                return self._to_review_queue_dict(queue)

            now = datetime.now(timezone.utc)
            extracted = _load_json_dict(queue.extracted_config_json)
            pack_data = _load_json_dict(queue.pack_data_json)

            self._ensure_selected_options_taxonomy(
                db=db,
                tenant_id=tenant_id,
                extracted=extracted,
                now=now,
            )

            system_prompt = self._generate_prompt_from_extracted(extracted)
            org_id = str(extracted.get("org_id", "")).strip()
            if not org_id:
                return {"error": {"reason_code": "PACK_CONFIG_ORG_ID_REQUIRED"}}

            persona_id = str(uuid4())
            persona = StudioPersonaModel(
                persona_id=persona_id,
                tenant_id=tenant_id,
                org_id=org_id,
                name=str(extracted.get("persona_name", "Imported Persona")) or "Imported Persona",
                slug=(
                    str(extracted.get("slug", "")).strip()
                    or f"imported-{persona_id[:8]}"
                ),
                role=str(extracted.get("role", "assistant")) or "assistant",
                scope="organization",
                enabled=True,
                model_profile="reasoning-optimized",
                system_prompt=system_prompt,
                persona_json=json.dumps(
                    {
                        "selected_options": extracted.get("selected_options", {}),
                        "guidelines": extracted.get("guidelines", {}),
                        "assigned_tools": extracted.get("assigned_tools", []),
                        "prefab_preferences": extracted.get("prefab_preferences", {}),
                        "success_criteria": extracted.get("success_criteria", ""),
                    }
                ),
                approval_status="approved",
                approved_by_user_id=installed_by_user_id,
                approved_at=now,
                created_by_user_id=installed_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(persona)

            manifest = pack_data.get("manifest", {}) if isinstance(pack_data.get("manifest"), dict) else {}
            bundle = PromptCatalogBundleModel(
                bundle_id=str(manifest.get("bundle_id", "")).strip() or str(uuid4()),
                tenant_id=tenant_id,
                bundle_version=str(manifest.get("bundle_version", "1.0.0")),
                checksum_sha256=str(manifest.get("checksum_sha256", "")),
                schema_version=str(manifest.get("schema_version", "v1")),
                signature_alg=str(manifest.get("signature_alg", "")),
                signature_key_id=str(manifest.get("signature_key_id", "")),
                signature_value=str(manifest.get("signature_value", "")),
                imported_by_user_id=installed_by_user_id,
                created_at=now,
            )
            db.add(bundle)

            queue.status = "installed"
            queue.installed_persona_id = persona_id
            queue.reviewed_by_user_id = installed_by_user_id
            queue.reviewed_at = now
            db.add(queue)
            db.commit()
            db.refresh(queue)
            return self._to_review_queue_dict(queue)


prompt_catalog_store = PromptCatalogStore()
