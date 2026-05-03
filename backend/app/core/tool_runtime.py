from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx


def _normalize_provider(provider_id: str | None, capability: str) -> str:
    direct = str(provider_id or "").strip().lower()
    if direct:
        return "google" if direct == "gemini" else direct
    if capability == "image_generation":
        return str(os.getenv("TOOL_PROVIDER_IMAGE_GENERATION", "google")).strip().lower()
    if capability == "email_send":
        return str(os.getenv("TOOL_PROVIDER_EMAIL_SEND", "email")).strip().lower()
    return ""


def get_tool_provider_status() -> dict[str, Any]:
    image_provider = _normalize_provider(None, "image_generation")
    email_provider = _normalize_provider(None, "email_send")
    return {
        "image_generation": {
            "selected_provider": image_provider,
            "openai_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "google_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        },
        "email_send": {
            "selected_provider": email_provider,
            "smtp_configured": bool(os.getenv("EMAIL_SMTP_HOST", "").strip()),
            "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY", "").strip()),
        },
    }


def generate_image_tool(*, prompt: str, provider_id: str | None, model_id: str | None) -> dict[str, Any]:
    provider = _normalize_provider(provider_id, "image_generation")
    model = str(model_id or "").strip()

    if provider == "openai":
        return _generate_image_openai(prompt=prompt, model_id=model or os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"))
    if provider == "google":
        return _generate_image_google(prompt=prompt, model_id=model or os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002"))

    return {
        "provider_id": provider or "simulated",
        "model_id": model or "simulated",
        "asset_url": f"simulated://images/{provider or 'simulated'}/{model or 'simulated'}",
        "mime_type": "image/png",
        "status": "simulated",
        "note": "Unsupported image provider; returned simulated output.",
    }


def _generate_image_openai(*, prompt: str, model_id: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "provider_id": "openai",
            "model_id": model_id,
            "asset_url": f"simulated://images/openai/{model_id}",
            "mime_type": "image/png",
            "status": "simulated",
            "note": "OPENAI_API_KEY missing.",
        }

    endpoint = os.getenv("OPENAI_IMAGE_ENDPOINT", "https://api.openai.com/v1/images/generations").strip()
    payload = {"model": model_id, "prompt": prompt, "size": "1024x1024", "response_format": "b64_json"}
    try:
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data", []) if isinstance(body, dict) else []
        b64 = ""
        if data and isinstance(data[0], dict):
            b64 = str(data[0].get("b64_json", ""))
        if b64:
            return {
                "provider_id": "openai",
                "model_id": model_id,
                "mime_type": "image/png",
                "status": "completed",
                "image_base64": b64,
                "byte_length_estimate": int((len(b64) * 3) / 4),
            }
    except Exception as error:
        return {
            "provider_id": "openai",
            "model_id": model_id,
            "asset_url": f"simulated://images/openai/{model_id}",
            "mime_type": "image/png",
            "status": "simulated",
            "note": f"OpenAI image generation fallback: {error}",
        }
    return {
        "provider_id": "openai",
        "model_id": model_id,
        "asset_url": f"simulated://images/openai/{model_id}",
        "mime_type": "image/png",
        "status": "simulated",
        "note": "OpenAI image response did not include image bytes.",
    }


def _generate_image_google(*, prompt: str, model_id: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "provider_id": "google",
            "model_id": model_id,
            "asset_url": f"simulated://images/google/{model_id}",
            "mime_type": "image/png",
            "status": "simulated",
            "note": "GEMINI_API_KEY missing.",
        }

    base = os.getenv("GEMINI_API_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    endpoint = f"{base}/models/{model_id}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    try:
        response = httpx.post(endpoint, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
        response.raise_for_status()
        body = response.json()
        candidates = body.get("candidates", []) if isinstance(body, dict) else []
        if candidates and isinstance(candidates[0], dict):
            content = candidates[0].get("content", {})
            if isinstance(content, dict):
                parts = content.get("parts", [])
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    inline_data = part.get("inlineData")
                    if isinstance(inline_data, dict):
                        mime = str(inline_data.get("mimeType", "image/png"))
                        data = str(inline_data.get("data", ""))
                        if data:
                            return {
                                "provider_id": "google",
                                "model_id": model_id,
                                "mime_type": mime,
                                "status": "completed",
                                "image_base64": data,
                                "byte_length_estimate": int((len(data) * 3) / 4),
                            }
    except Exception as error:
        return {
            "provider_id": "google",
            "model_id": model_id,
            "asset_url": f"simulated://images/google/{model_id}",
            "mime_type": "image/png",
            "status": "simulated",
            "note": f"Google image generation fallback: {error}",
        }

    return {
        "provider_id": "google",
        "model_id": model_id,
        "asset_url": f"simulated://images/google/{model_id}",
        "mime_type": "image/png",
        "status": "simulated",
        "note": "Google response did not include inline image data.",
    }


def send_email_tool(*, sender: str, recipients: list[str], subject: str, body: str) -> dict[str, Any]:
    provider = _normalize_provider(None, "email_send")
    if provider in {"smtp", "email"}:
        return _send_email_smtp(sender=sender, recipients=recipients, subject=subject, body=body)
    if provider == "sendgrid":
        return _send_email_sendgrid(sender=sender, recipients=recipients, subject=subject, body=body)
    return {
        "provider_id": provider or "email-simulated",
        "status": "simulated",
        "note": "Unsupported email provider. Simulated send accepted.",
    }


def _send_email_smtp(*, sender: str, recipients: list[str], subject: str, body: str) -> dict[str, Any]:
    host = os.getenv("EMAIL_SMTP_HOST", "").strip()
    port = int(os.getenv("EMAIL_SMTP_PORT", "587") or 587)
    username = os.getenv("EMAIL_SMTP_USERNAME", "").strip()
    password = os.getenv("EMAIL_SMTP_PASSWORD", "").strip()
    use_tls = os.getenv("EMAIL_SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}

    if not host:
        return {"provider_id": "smtp", "status": "simulated", "note": "EMAIL_SMTP_HOST missing."}

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return {"provider_id": "smtp", "status": "sent"}
    except Exception as error:
        return {"provider_id": "smtp", "status": "simulated", "note": f"SMTP send fallback: {error}"}


def _send_email_sendgrid(*, sender: str, recipients: list[str], subject: str, body: str) -> dict[str, Any]:
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
    if not api_key:
        return {"provider_id": "sendgrid", "status": "simulated", "note": "SENDGRID_API_KEY missing."}
    payload = {
        "personalizations": [{"to": [{"email": item} for item in recipients]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return {"provider_id": "sendgrid", "status": "sent"}
    except Exception as error:
        return {"provider_id": "sendgrid", "status": "simulated", "note": f"SendGrid fallback: {error}"}
