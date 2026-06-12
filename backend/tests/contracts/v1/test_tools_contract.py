from fastapi.testclient import TestClient

from app.main import app
from tests.contracts.v1._auth_helpers import register_and_login


def test_tools_image_and_email_contract() -> None:
    client = TestClient(app)
    auth_headers = register_and_login(client, scope_org_id="org0")

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
