from __future__ import annotations

import io
import re

from pypdf import PdfReader


def _normalize_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    return collapsed


def _truncate(value: str, *, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def extract_document_text(*, content: bytes, content_type: str, filename: str) -> str:
    lowered_type = (content_type or "").lower()
    lowered_name = (filename or "").lower()

    if "pdf" in lowered_type or lowered_name.endswith(".pdf"):
        return extract_pdf_text(content)
    if lowered_type.startswith("text/") or lowered_name.endswith((".txt", ".md", ".json", ".csv", ".py", ".ts", ".tsx", ".js", ".fs", ".cs")):
        try:
            return _truncate(_normalize_text(content.decode("utf-8", errors="ignore")))
        except Exception:
            return ""
    return ""


def extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception:
        return ""

    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            parts.append(text)
    joined = "\n".join(parts)
    return _truncate(_normalize_text(joined))
