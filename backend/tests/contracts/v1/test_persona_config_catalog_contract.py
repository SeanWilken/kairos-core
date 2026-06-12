from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_persona_config_catalog_import_export_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="catalog.owner@myai.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Catalog Org", "slug": "catalog-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    import_payload = {
        "manifest": {
            "bundle_id": "bundle-dev-v1",
            "bundle_version": "1.0.0",
            "schema_version": "v1",
        },
        "config": {
            "persona_name": "Imported Catalog Persona",
            "slug": "imported-catalog-persona",
            "role": "assistant",
            "industry": "developer",
            "primary_role": "developer",
            "org_id": org_id,
        },
        "selected_options": {
            "communication_style": "balanced",
            "personality_traits": ["methodical"],
            "initiative_level": "moderate",
        },
        "guidelines": {
            "do_list": ["Be clear"],
            "dont_list": ["Ignore user context"],
            "guardrails": ["Never bypass safety"],
        },
        "assigned_tools": ["notes_summary"],
        "prefab_preferences": {"industry": "developer", "role": "general"},
        "success_criteria": "User gets actionable help.",
        "categories": [
            {
                "name": "communication_style",
                "display_name": "Communication Style",
                "description": "How responses should be expressed",
                "sort_order": 1,
            }
        ],
        "options": [
            {
                "category_name": "communication_style",
                "key": "concise",
                "label": "Concise",
                "verbose_statement": "Respond with brevity and directness.",
                "provider_compatibility": ["openai", "anthropic"],
                "sort_order": 1,
            }
        ],
        "prefabs": [
            {
                "industry": "developer",
                "role": "general",
                "segment_type": "system_base",
                "name": "Developer Base",
                "content": "You are an expert software developer assistant.",
                "variables": {},
                "tokens_estimate": 20,
                "version": 1,
            }
        ],
        "personas": [],
    }

    dry_run = client.post("/v1/persona-config/import?dry_run=true", headers=headers, json=import_payload)
    assert dry_run.status_code == 200
    computed = dry_run.json()["data"]["computed_checksum_sha256"]

    import_payload["manifest"]["checksum_sha256"] = computed
    imported = client.post("/v1/persona-config/import", headers=headers, json=import_payload)
    assert imported.status_code == 200
    queue_id = imported.json()["data"]["queue_id"]
    assert imported.json()["data"]["status"] in {"pending_review", "rejected"}

    review = client.get(f"/v1/reviews/packs/{queue_id}", headers=headers)
    assert review.status_code == 200
    assert review.json()["data"]["queue_id"] == queue_id

    required_cases = [
        "greeting",
        "do_list_check",
        "dont_list_check",
        "boundary_test",
        "safety_test",
        "role_check",
    ]
    for case in required_cases:
        case_response = client.post(
            f"/v1/reviews/packs/{queue_id}/conversation",
            headers=headers,
            json={
                "test_case_key": case,
                "prompt": f"test prompt {case}",
                "response": f"test response {case}",
                "passed": True,
            },
        )
        assert case_response.status_code == 200

    approved = client.post(
        f"/v1/reviews/packs/{queue_id}/decision",
        headers=headers,
        json={"decision": "approve", "review_notes": "Looks safe and validated."},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"

    installed = client.post(f"/v1/reviews/packs/{queue_id}/install", headers=headers)
    assert installed.status_code == 200
    assert installed.json()["data"]["status"] == "installed"
    assert isinstance(installed.json()["data"]["installed_persona_id"], str)

    exported = client.get("/v1/persona-config/export", headers=headers)
    assert exported.status_code == 200
    body = exported.json()["data"]
    assert body["manifest"]["schema_version"] == "v1"
    assert isinstance(body["manifest"]["checksum_sha256"], str)


def test_persona_config_import_checksum_mismatch_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="catalog.checksum@myai.dev")

    response = client.post(
        "/v1/persona-config/import",
        headers=headers,
        json={
            "manifest": {
                "bundle_id": "bundle-bad",
                "bundle_version": "1.0.0",
                "schema_version": "v1",
                "checksum_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
            "categories": [],
            "options": [],
            "prefabs": [],
            "personas": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["reason_code"] == "PROMPT_CATALOG_CHECKSUM_MISMATCH"


def test_pack_review_requires_all_structured_cases_before_approval() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="catalog.required@myai.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "Required Cases Org", "slug": "required-cases-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    payload = {
        "manifest": {"bundle_id": "bundle-required", "bundle_version": "1.0.0", "schema_version": "v1"},
        "config": {
            "persona_name": "Required Cases Persona",
            "slug": "required-cases-persona",
            "role": "assistant",
            "org_id": org_id,
        },
    }
    dry = client.post("/v1/persona-config/import?dry_run=true", headers=headers, json=payload)
    assert dry.status_code == 200
    payload["manifest"]["checksum_sha256"] = dry.json()["data"]["computed_checksum_sha256"]

    queued = client.post("/v1/persona-config/import", headers=headers, json=payload)
    assert queued.status_code == 200
    queue_id = queued.json()["data"]["queue_id"]

    one_case = client.post(
        f"/v1/reviews/packs/{queue_id}/conversation",
        headers=headers,
        json={"test_case_key": "greeting", "prompt": "hi", "response": "hello", "passed": True},
    )
    assert one_case.status_code == 200

    approve = client.post(
        f"/v1/reviews/packs/{queue_id}/decision",
        headers=headers,
        json={"decision": "approve", "review_notes": "insufficient coverage"},
    )
    assert approve.status_code == 422
    assert (
        approve.json()["error"]["details"]["reason_code"]
        == "PACK_REVIEW_REQUIRED_CASES_INCOMPLETE"
    )


def test_persona_config_persona_import_contract() -> None:
    client = TestClient(app)
    headers = register_and_login(client, email="catalog.oneoff@myai.dev")

    org = client.post(
        "/v1/studio/organizations",
        headers=headers,
        json={"name": "One Off Org", "slug": "one-off-org", "mode": "team"},
    )
    assert org.status_code == 200
    org_id = org.json()["data"]["org_id"]

    payload = {
        "name": "Visual Architect",
        "role": "design-strategist",
        "industry": "saas",
        "headline": "Deliver visual design concepts with rationale.",
        "summary": "Create high-conviction visual direction for product work.",
        "orgId": org_id,
        "modelProfile": "reasoning-optimized",
        "traits": ["systematic", "creative"],
        "communicationStyle": "balanced",
        "initiativeLevel": "proactive",
        "tone": "professional",
        "doList": "Show options\nExplain tradeoffs",
        "dontList": "Assume unverified facts",
        "guardrails": "Respect approvals",
        "tools": ["nano_banana", "email_send"],
    }

    dry_run = client.post("/v1/persona-config/import/persona?dry_run=true", headers=headers, json=payload)
    assert dry_run.status_code == 200
    dry_data = dry_run.json()["data"]
    assert dry_data["dry_run"] is True
    assert dry_data["wizard_prefill"]["config"]["org_id"] == org_id
    assert dry_data["wizard_prefill"]["assigned_tools"] == ["nano_banana", "email_send"]

    queued = client.post("/v1/persona-config/import/persona", headers=headers, json=payload)
    assert queued.status_code == 200
    queue_data = queued.json()["data"]
    assert queue_data["status"] in {"pending_review", "rejected"}
    assert isinstance(queue_data.get("computed_checksum_sha256"), str)

    queue_id = queue_data["queue_id"]
    for case in ["greeting", "do_list_check", "dont_list_check", "boundary_test", "safety_test", "role_check"]:
        case_response = client.post(
            f"/v1/reviews/packs/{queue_id}/conversation",
            headers=headers,
            json={
                "test_case_key": case,
                "prompt": f"test prompt {case}",
                "response": f"test response {case}",
                "passed": True,
            },
        )
        assert case_response.status_code == 200

    approved = client.post(
        f"/v1/reviews/packs/{queue_id}/decision",
        headers=headers,
        json={"decision": "approve", "review_notes": "approved"},
    )
    assert approved.status_code == 200

    installed = client.post(f"/v1/reviews/packs/{queue_id}/install", headers=headers)
    assert installed.status_code == 200
    assert installed.json()["data"]["status"] == "installed"

    categories = client.get("/v1/persona-config/templates/categories", headers=headers)
    assert categories.status_code == 200
    names = {str(item.get("name")) for item in categories.json()["data"]["items"]}
    assert "communication_style" in names
    assert "personality_traits" in names

    options = client.get("/v1/persona-config/templates/options/communication_style", headers=headers)
    assert options.status_code == 200
    option_keys = {str(item.get("key")) for item in options.json()["data"]["items"]}
    assert "balanced" in option_keys
