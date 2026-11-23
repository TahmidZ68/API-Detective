"""Log and error trace analyzer tool."""

from __future__ import annotations

import re
from typing import Any

from backend.app.core.security import redact_text

HTTP_STATUS_IN_LOG_RE = re.compile(r"\b(?:HTTP/\d\.\d\s+|status(?:_code)?[=:\s]+)([1-5]\d\d)\b", re.IGNORECASE)
FILE_LINE_RE = re.compile(r'([A-Za-z0-9_./\\-]+\.(?:py|ts|tsx|js|jsx))["\',:\s]+(?:line\s+)?(\d+)', re.IGNORECASE)


def analyze_error_log(error_text: str | None) -> dict[str, Any]:
    """Extract status codes, exception classes, and source file/line references from error text."""
    if not error_text or not error_text.strip():
        return {
            "status_codes": [],
            "source_locations": [],
            "keywords": [],
            "sanitized_log": "",
        }

    sanitized = redact_text(error_text)
    statuses = [int(s) for s in HTTP_STATUS_IN_LOG_RE.findall(sanitized)]
    locations = [
        {"file": match[0], "line": int(match[1])}
        for match in FILE_LINE_RE.findall(sanitized)
    ]

    lower = sanitized.lower()
    keywords: list[str] = []
    for kw in (
        "unauthorized",
        "forbidden",
        "not found",
        "timeout",
        "connection refused",
        "ssl",
        "cors",
        "jsondecodeerror",
        "validationerror",
        "rate limit",
        "too many requests",
    ):
        if kw in lower:
            keywords.append(kw)

    return {
        "status_codes": statuses,
        "source_locations": locations,
        "keywords": keywords,
        "sanitized_log": sanitized[:2000],
    }
