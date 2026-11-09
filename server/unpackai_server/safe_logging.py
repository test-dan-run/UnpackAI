"""Logging setup that keeps the API key and request headers out of the logs.

The setup does four things:

1. It removes ANTHROPIC_LOG from the environment, because the SDK's debug
   logging prints request options.
2. It caps the SDK and HTTP client loggers at WARNING, so no library logs a
   request or its headers, even when the root logger is set to DEBUG.
3. It adds a filter to every handler that replaces the API key, and any
   x-api-key or Authorization header value, with [REDACTED]. The filter is a
   second line of defense in case a library logs a header anyway.
4. The server's own request log (see app.py) writes only the method, the path,
   the status code, and the time taken. It never writes headers or bodies.
"""
from __future__ import annotations

import logging
import os
import re

QUIET_LOGGERS = ("anthropic", "anthropic._base_client", "httpx", "httpx2", "httpcore", "httpcore2", "hpack", "keyring")

HEADER_PATTERN = re.compile(
    r"""(?ix)
    (x-api-key|authorization|proxy-authorization)   # header name
    (['"]?\s*[:=,]\s*\(?\s*b?['"]?)                  # separator as it appears in dicts, tuples, or raw headers
    ([^'"\s,)]+(?:\s+[^'"\s,)]+)?)                   # value, e.g., "Bearer abc"
    """
)
KEY_SHAPE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


class RedactSecrets(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()

    def add_secret(self, value: str) -> None:
        if value and len(value) >= 8:
            self._secrets.add(value)

    def redact(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "[REDACTED]")
        text = HEADER_PATTERN.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)
        return KEY_SHAPE.sub("[REDACTED]", text)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        clean = self.redact(message)
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        if clean != message:
            record.msg, record.args = clean, None
        return True


REDACTOR = RedactSecrets()


def _attach(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        if REDACTOR not in handler.filters:
            handler.addFilter(REDACTOR)


def configure_logging(level: int = logging.INFO) -> None:
    os.environ.pop("ANTHROPIC_LOG", None)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)
    for name in QUIET_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(logging.WARNING)
        _attach(lg)
    _attach(root)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        _attach(logging.getLogger(name))


def uvicorn_log_config() -> dict:
    """Log config for uvicorn that attaches the redaction filter to its handlers."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"redact": {"()": lambda: REDACTOR}},
        "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
        "handlers": {
            "default": {"class": "logging.StreamHandler", "formatter": "plain", "filters": ["redact"]},
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            # The server writes its own request log without headers, so the
            # uvicorn access log is turned off.
            "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
        },
    }
