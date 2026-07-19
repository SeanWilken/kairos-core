from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def render_pdf_document(*, title: str, content: str, command_template: str) -> tuple[bytes, str, str]:
    template = str(command_template or "").strip()
    if not template:
        raise RuntimeError("PDF render command template is not configured.")

    safe_title = "".join(ch for ch in (title or "document") if ch.isalnum() or ch in {"-", "_", " "}).strip() or "document"
    filename = f"{safe_title}.pdf".replace(" ", "-")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.md"
        output_path = Path(tmpdir) / filename
        input_path.write_text(content, encoding="utf-8")

        command = template.format(input=str(input_path), output=str(output_path), title=title or safe_title)
        completed = subprocess.run(command, shell=True, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "PDF render command failed")
        if not output_path.exists():
            raise RuntimeError("PDF render command did not produce output.")
        return output_path.read_bytes(), "application/pdf", filename
