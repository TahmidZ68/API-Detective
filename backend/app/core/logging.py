"""Structured logging setup with automatic secret redaction."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from backend.app.core.security import redact_object, redact_text


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON lines with secret redaction."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": redact_text(record.getMessage()),
        }
        extra_data = getattr(record, "structured_data", None)
        if isinstance(extra_data, dict):
            payload.update(redact_object(extra_data))
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class StructuredLogger:
    """Compatibility wrapper providing structlog-style keyword logging."""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        self._logger.log(level, event, extra={"structured_data": kwargs})

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)


def configure_logging(level: str = "INFO") -> None:
    """Configure root structured logging."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not any(isinstance(h.formatter, StructuredJSONFormatter) for h in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(StructuredJSONFormatter())
        root.handlers = [handler]


def get_logger(name: str = "api_detective") -> StructuredLogger:
    """Return a structured logger instance."""
    return StructuredLogger(name)
