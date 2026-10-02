"""Structured logging (JSON in CI/production, console locally). Never log secrets."""

from __future__ import annotations

import logging
import sys

import structlog

from hudhud.config import get_settings

_SECRET_KEYS = ("api_key", "token", "password", "secret", "authorization")


def _redact(_logger, _name, event_dict):
    for key in list(event_dict):
        if any(s in key.lower() for s in _SECRET_KEYS):
            event_dict[key] = "***"
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(stream=sys.stderr, level=level, format="%(message)s")
    renderer = structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
