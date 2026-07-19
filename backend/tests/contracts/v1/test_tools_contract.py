from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_tools_image_and_email_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

    catalog = client.get("/v1/tools/catalog", headers=auth_headers)
    assert catalog.status_code == 200
    catalog_data = catalog.json()["data"]
    assert isinstance(catalog_data.get("tools"), list)
    tool_ids = {item.get("tool_id") for item in catalog_data.get("tools", []) if isinstance(item, dict)}
    assert "speech_to_text" in tool_ids
    assert "text_to_speech" in tool_ids
    assert "image_generate" in tool_ids
    assert "pdf_generate" in tool_ids

    runtime_registry = client.get("/v1/tools/runtime-registry", headers=auth_headers)
    assert runtime_registry.status_code == 200
    registry_data = runtime_registry.json()["data"]
    assert isinstance(registry_data.get("items"), list)
    registry_tool_ids = {item.get("tool_id") for item in registry_data.get("items", []) if isinstance(item, dict)}
    assert "speech_to_text" in registry_tool_ids
    assert "text_to_speech" in registry_tool_ids

    with patch(
        "app.api.v1.routes.tools.transcribe_audio",
        return_value={"text": "hello from wrapper stt", "provider": "whisper_cpp", "language": "en", "segments": [], "raw": {}},
    ):
        stt_response = client.post(
            "/v1/tools/speech/transcribe",
            headers=auth_headers,
            data={"org_id": "org0", "language": "en"},
            files={"file": ("sample.wav", b"RIFF....", "audio/wav")},
        )
    assert stt_response.status_code == 200
    stt_data = stt_response.json()["data"]
    assert stt_data["text"] == "hello from wrapper stt"
    assert stt_data["execution"]["tool_id"] == "speech_to_text"

    with patch(
        "app.api.v1.routes.tools.synthesize_speech",
        return_value=(b"RIFF....", "audio/wav", "speech.wav"),
    ):
        tts_response = client.post(
            "/v1/tools/speech/synthesize",
            headers=auth_headers,
            json={"org_id": "org0", "text": "hello", "voice": "amy", "format": "wav", "tone": "warm", "cadence": "measured"},
        )
    assert tts_response.status_code == 200
    assert tts_response.headers["content-type"].startswith("audio/wav")
    assert tts_response.headers.get("x-tool-execution-id")

    with patch(
        "app.api.v1.routes.tools.generate_image_tool",
        return_value={"provider_id": "google", "model_id": "imagen-3.0-generate-002", "mime_type": "image/png", "status": "completed"},
    ):
        image_profile_response = client.post(
            "/v1/tools/image/generate",
            headers=auth_headers,
            json={
                "org_id": "org0",
                "prompt": "Create a homepage hero mockup",
                "profile_id": "document-drafter",
                "tool_id": "nano_banana",
            },
        )
    assert image_profile_response.status_code == 200
    assert image_profile_response.json()["data"]["provider_id"] == "google"

    class _DraftResult:
        def __init__(self) -> None:
            self.content = "# Generated Draft\n\nSome markdown"
            self.provider = "anthropic"
            self.model = "claude-sonnet-4-20250514"
            self.usage = {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22}

    with patch("app.api.v1.routes.tools.model_gateway.generate_text", return_value=_DraftResult()):
        draft_response = client.post(
            "/v1/tools/documents/draft",
            headers=auth_headers,
            json={
                "org_id": "org0",
                "title": "Deployment Guide",
                "prompt": "Draft a deployment walkthrough",
                "profile_id": "document-drafter",
                "output_profile": "walkthrough",
            },
        )
    assert draft_response.status_code == 200
    draft_data = draft_response.json()["data"]
    assert draft_data["provider_id"] == "anthropic"
    assert draft_data["output_profile"] == "walkthrough"
    assert draft_data["execution"]["tool_id"] == "document_create_markdown"

    task_response = client.post(
        "/v1/tools/tasks/create",
        headers=auth_headers,
        json={
            "org_id": "org0",
            "prompt": "Investigate deployment blocker and summarize findings",
            "profile_id": "project-manager",
            "visibility": "org_public",
            "status": "todo",
            "tags": ["deployment"],
        },
    )
    assert task_response.status_code == 200
    task_data = task_response.json()["data"]
    assert task_data["task"]["title"].startswith("Investigate deployment blocker")
    assert task_data["execution"]["tool_id"] == "task_create"

    class _WorkflowResult:
        def __init__(self) -> None:
            self.content = "# Workflow\n\n## Objective\n..."
            self.provider = "anthropic"
            self.model = "claude-sonnet-4-20250514"
            self.usage = {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22}

    with patch("app.api.v1.routes.tools.model_gateway.generate_text", return_value=_WorkflowResult()):
        workflow_response = client.post(
            "/v1/tools/workflows/scaffold",
            headers=auth_headers,
            json={
                "org_id": "org0",
                "title": "Release Workflow",
                "prompt": "Create a release workflow",
                "profile_id": "scrum-master",
                "output_profile": "walkthrough",
            },
        )
    assert workflow_response.status_code == 200
    workflow_data = workflow_response.json()["data"]
    assert workflow_data["provider_id"] == "anthropic"
    assert workflow_data["execution"]["tool_id"] == "workflow_create"

    with patch(
        "app.api.v1.routes.tools.render_pdf_document",
        return_value=(b"%PDF-1.4", "application/pdf", "deployment-guide.pdf"),
    ):
        pdf_response = client.post(
            "/v1/tools/documents/render-pdf",
            headers=auth_headers,
            json={
                "org_id": "org0",
                "title": "Deployment Guide",
                "content": "# Deployment Guide\n\nSteps here",
                "profile_id": "document-drafter",
            },
        )
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.headers.get("x-tool-execution-id")

    provider_status = client.get("/v1/tools/providers/status", headers=auth_headers)
    assert provider_status.status_code == 200
    provider_data = provider_status.json()["data"]
    assert isinstance(provider_data.get("image_generation"), dict)
    assert isinstance(provider_data.get("email_send"), dict)
    assert isinstance(provider_data.get("providers"), list)
    google_provider = next(
        (item for item in provider_data.get("providers", []) if item.get("provider_id") == "google"),
        {},
    )
    google_tools = google_provider.get("tools", []) if isinstance(google_provider, dict) else []
    assert any(tool.get("tool_id") == "nano_banana" for tool in google_tools if isinstance(tool, dict))

    image_response = client.post(
        "/v1/tools/image/generate",
        headers=auth_headers,
        json={
            "org_id": "org0",
            "prompt": "Create a homepage hero mockup",
            "provider_id": "google",
            "model_id": "imagen-3.0-generate-002",
            "tool_id": "nano_banana",
        },
    )
    assert image_response.status_code == 200
    image_data = image_response.json()["data"]
    assert image_data["tool_id"] == "nano_banana"
    assert image_data["output"]["mime_type"] == "image/png"

    email_response = client.post(
        "/v1/tools/email/send",
        headers=auth_headers,
        json={
            "org_id": "org0",
            "sender": "noreply@myai.dev",
            "recipients": ["user@example.com"],
            "subject": "Test",
            "body": "Hello from tools API",
        },
    )
    assert email_response.status_code == 200
    email_data = email_response.json()["data"]
    assert email_data["status"] in {"sent", "simulated"}
    assert isinstance(email_data.get("transport"), dict)

    list_exec = client.get("/v1/tools/executions", headers=auth_headers, params={"org_id": "org0"})
    assert list_exec.status_code == 200
    assert isinstance(list_exec.json()["data"]["items"], list)

    list_emails = client.get("/v1/tools/email/messages", headers=auth_headers, params={"org_id": "org0"})
    assert list_emails.status_code == 200
    assert isinstance(list_emails.json()["data"]["items"], list)
