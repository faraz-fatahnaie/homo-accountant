"""Safe HTTP header helpers."""

from __future__ import annotations

import re
from urllib.parse import quote


def attachment_disposition(filename: str) -> str:
    """Build a CRLF-safe, Unicode-compatible attachment disposition."""
    clean = filename.replace("\r", "").replace("\n", "").replace('"', "").strip()
    clean = clean[:255] or "download"
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", clean) or "download"
    encoded = quote(clean, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"
