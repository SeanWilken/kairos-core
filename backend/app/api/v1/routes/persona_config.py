from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.auth_context import require_authentication, require_roles
from app.core.prompt_catalog_store import checksum_sha256, prompt_catalog_store
from app.core.response import ok_response

router = APIRouter(prefix="/persona-config", tags=["persona-config"])


class PersonaImportPayload(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    industry: str = ""
    headline: str = ""
    summary: str = ""
    orgId: str = Field(min_length=1)
    scope: str = "organization"
    modelProfile: str = "reasoning-optimized"
    traits: list[str] = Field(default_factory=list)
    communicationStyle: str = "balanced"
    initiativeLevel: str = "moderate"
    tone: str = "professional"
    doList: str = ""
    dontList: str = ""
    guardrails: str = ""
    tools: list[str] = Field(default_factory=list)
    systemPromptOverride: str = ""


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _slugify(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    normalized = "-".join(part for part in lowered.split("-") if part)
    return normalized or "persona"


def _persona_import_to_pack(payload: PersonaImportPayload) -> dict[str, Any]:
    persona_slug = _slugify(payload.name)
    return {
        "schema_version": "v2",
        "manifest": {
            "schema_version": "v1",
            "source": "persona_import",
            "pack_name": payload.name,
            "checksum_sha256": "",
        },
        "config": {
            "org_id": payload.orgId,
            "persona_name": payload.name,
            "role": payload.role,
            "industry": payload.industry,
            "description": payload.summary,
        },
        "selected_options": {
            "personality_traits": payload.traits,
            "communication_style": payload.communicationStyle,
            "initiative_level": payload.initiativeLevel,
            "tone": payload.tone,
        },
        "guidelines": {
            "do_list": _split_lines(payload.doList),
            "dont_list": _split_lines(payload.dontList),
            "guardrails": _split_lines(payload.guardrails),
        },
        "assigned_tools": payload.tools,
        "success_criteria": payload.headline or payload.summary,
        "personas": [
            {
                "name": payload.name,
                "slug": persona_slug,
                "role": payload.role,
                "scope": payload.scope,
                "model_profile": payload.modelProfile,
                "runtime_provider_id": "",
                "runtime_model_id": "",
                "system_prompt": payload.systemPromptOverride,
            }
        ],
    }


@router.post("/import/persona")
def import_persona(
    request: Request,
    payload: PersonaImportPayload,
    dry_run: bool = Query(default=False),
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})

    bundle = _persona_import_to_pack(payload)
    manifest = bundle.get("manifest", {}) if isinstance(bundle.get("manifest"), dict) else {}
    checksum_body = {
        "schema_version": bundle.get("schema_version", "v2"),
        "config": bundle.get("config", {}),
        "selected_options": bundle.get("selected_options", {}),
        "guidelines": bundle.get("guidelines", {}),
        "assigned_tools": bundle.get("assigned_tools", []),
        "success_criteria": bundle.get("success_criteria", ""),
        "personas": bundle.get("personas", []),
    }
    checksum_value = checksum_sha256(checksum_body)
    bundle["manifest"] = {**manifest, "checksum_sha256": checksum_value}

    extracted = prompt_catalog_store.extract_safe_pack_config(payload=bundle)
    safety = prompt_catalog_store.safety_scan_pack(payload=bundle)

    if dry_run:
        return ok_response(
            request,
            data={
                "dry_run": True,
                "computed_checksum_sha256": checksum_value,
                "extracted_config": extracted,
                "safety_flags": safety,
                "wizard_prefill": {
                    "config": bundle.get("config", {}),
                    "selected_options": bundle.get("selected_options", {}),
                    "guidelines": bundle.get("guidelines", {}),
                    "assigned_tools": bundle.get("assigned_tools", []),
                    "personas": bundle.get("personas", []),
                },
            },
        )

    queued = prompt_catalog_store.enqueue_pack_review(
        tenant_id=auth.tenant_id,
        payload=bundle,
        extracted_config=extracted,
        safety_flags=safety,
    )
    return ok_response(
        request,
        data={
            **queued,
            "computed_checksum_sha256": checksum_value,
            "wizard_prefill": {
                "config": bundle.get("config", {}),
                "selected_options": bundle.get("selected_options", {}),
                "guidelines": bundle.get("guidelines", {}),
                "assigned_tools": bundle.get("assigned_tools", []),
                "personas": bundle.get("personas", []),
            },
        },
    )


@router.get("/templates/categories")
def list_template_categories(request: Request) -> dict[str, Any]:
    auth = require_authentication(request)
    categories = prompt_catalog_store.list_categories(tenant_id=auth.tenant_id)
    return ok_response(request, data={"items": categories})


@router.get("/templates/options/{category_name}")
def list_template_options(request: Request, category_name: str) -> dict[str, Any]:
    auth = require_authentication(request)
    options = prompt_catalog_store.list_options(
        tenant_id=auth.tenant_id,
        category_name=category_name,
    )
    return ok_response(request, data={"items": options})


@router.get("/prefabs")
def list_prefabs(
    request: Request,
    industry: str | None = Query(default=None),
    role: str | None = Query(default=None),
) -> dict[str, Any]:
    auth = require_authentication(request)
    prefabs = prompt_catalog_store.list_prefabs(
        tenant_id=auth.tenant_id,
        industry=industry,
        role=role,
    )
    return ok_response(request, data={"items": prefabs})


@router.get("/export")
def export_catalog(request: Request, org_id: str | None = Query(default=None)) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})
    if org_id and not auth.is_global_admin and auth.org_id != org_id:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Operation is outside current organization scope.",
                "details": {"reason_code": "ORG_SCOPE_FORBIDDEN"},
            },
        )

    bundle = prompt_catalog_store.export_bundle(tenant_id=auth.tenant_id, org_id=org_id)
    computed_checksum = checksum_sha256(bundle)
    return ok_response(
        request,
        data={
            "manifest": {
                "schema_version": "v1",
                "checksum_sha256": computed_checksum,
                "signature_alg": "",
                "signature_key_id": "",
                "signature_value": "",
            },
            **bundle,
        },
    )


@router.post("/import")
def import_catalog(
    request: Request,
    payload: dict[str, Any],
    dry_run: bool = Query(default=False),
) -> dict[str, Any]:
    auth = require_authentication(request)
    require_roles(auth, {"owner", "admin"})

    if "generated_prompt" in payload:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "generated_prompt is not accepted in import payloads.",
                "details": {"reason_code": "PROMPT_CATALOG_GENERATED_PROMPT_FORBIDDEN"},
            },
        )

    normalized = prompt_catalog_store.normalize_import_payload(payload=payload)
    if "error" in normalized:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Pack import schema is not recognized.",
                "details": normalized["error"],
            },
        )

    body = normalized["payload"]
    normalized_errors = list(normalized.get("errors", []))
    validation = prompt_catalog_store.validate_normalized_import_payload(payload=body)
    validation_errors = normalized_errors + list(validation.get("errors", []))
    if validation_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Pack import payload validation failed.",
                "details": {
                    "reason_code": "PACK_IMPORT_VALIDATION_FAILED",
                    "errors": validation_errors,
                },
            },
        )

    checksum_body = {
        "schema_version": body.get("schema_version", "v2"),
        "config": body.get("config", {}),
        "selected_options": body.get("selected_options", {}),
        "guidelines": body.get("guidelines", {}),
        "assigned_tools": body.get("assigned_tools", []),
        "prefab_preferences": body.get("prefab_preferences", {}),
        "success_criteria": body.get("success_criteria", ""),
        "categories": body.get("categories", []),
        "options": body.get("options", []),
        "prefabs": body.get("prefabs", []),
        "personas": body.get("personas", []),
        "tools": body.get("tools", []),
        "quick_config": body.get("quick_config", {}),
        "user_profile_template": body.get("user_profile_template", {}),
    }
    computed_checksum = checksum_sha256(checksum_body)
    manifest = body.get("manifest", {}) if isinstance(body.get("manifest"), dict) else {}
    provided_checksum = str(manifest.get("checksum_sha256", "")).strip().lower()
    if provided_checksum and provided_checksum != computed_checksum:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Catalog checksum mismatch.",
                "details": {
                    "reason_code": "PROMPT_CATALOG_CHECKSUM_MISMATCH",
                    "provided_checksum_sha256": provided_checksum,
                    "computed_checksum_sha256": computed_checksum,
                },
            },
        )

    warnings = list(normalized.get("warnings", [])) + list(validation.get("warnings", []))

    if dry_run:
        extracted = prompt_catalog_store.extract_safe_pack_config(payload=body)
        safety = prompt_catalog_store.safety_scan_pack(payload=body)
        return ok_response(
            request,
            data={
                "dry_run": True,
                "detected_schema": normalized.get("schema"),
                "manifest": {
                    **manifest,
                    "checksum_sha256": provided_checksum or computed_checksum,
                },
                "computed_checksum_sha256": computed_checksum,
                "extracted_config": extracted,
                "safety_flags": safety,
                "warnings": warnings,
                "counts": {
                    "categories": len(body.get("categories", [])),
                    "options": len(body.get("options", [])),
                    "prefabs": len(body.get("prefabs", [])),
                    "personas": len(body.get("personas", [])),
                    "tools": len(body.get("tools", [])),
                },
            },
        )

    full_payload = {
        "manifest": {
            **manifest,
            "checksum_sha256": provided_checksum or computed_checksum,
        },
        **body,
    }
    extracted = prompt_catalog_store.extract_safe_pack_config(payload=full_payload)
    safety = prompt_catalog_store.safety_scan_pack(payload=full_payload)
    queued = prompt_catalog_store.enqueue_pack_review(
        tenant_id=auth.tenant_id,
        payload=full_payload,
        extracted_config=extracted,
        safety_flags=safety,
    )
    return ok_response(
        request,
        data={
            **queued,
            "detected_schema": normalized.get("schema"),
            "warnings": warnings,
            "computed_checksum_sha256": computed_checksum,
            "signature_ready": {
                "signature_alg": str(manifest.get("signature_alg") or ""),
                "signature_key_id": str(manifest.get("signature_key_id") or ""),
                "signature_value": str(manifest.get("signature_value") or ""),
            },
        },
    )
