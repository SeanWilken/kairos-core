from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.core.config import get_settings


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _sign(signing_input: bytes) -> bytes:
    secret = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, signing_input, hashlib.sha256).digest()


def issue_jwt(payload: dict[str, Any], *, token_type: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    token_payload = {
        **payload,
        "token_type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": str(uuid4()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(
        json.dumps(token_payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature_segment = _b64url_encode(_sign(signing_input))
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_jwt(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token.")

    header_segment, payload_segment, signature_segment = parts
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = _b64url_encode(_sign(signing_input))
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise ValueError("Invalid token signature.")

    payload_bytes = _b64url_decode(payload_segment)
    payload = json.loads(payload_bytes.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid token payload.")

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise ValueError("Token missing expiry.")
    if datetime.now(timezone.utc).timestamp() >= exp:
        raise ValueError("Token expired.")

    return payload


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_password_hash(password: str) -> str:
    iterations = 390000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iterations_raw, salt, digest_raw = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        expected = _b64url_decode(digest_raw)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False
