"""
Wiii Structured Logging — SOTA 2026

Configures structlog for JSON output (production) or colored console (development).
Integrates with stdlib logging so all existing `logging.getLogger()` calls
automatically emit structured output.

Usage:
    from app.core.logging_config import setup_logging
    setup_logging()  # Call once at app startup
"""

import logging
import sys

import structlog


def setup_logging(*, json_output: bool = False, log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.

    Args:
        json_output: True for JSON lines (production), False for colored console (dev).
        log_level: Root log level string (DEBUG, INFO, WARNING, ERROR).
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    for noisy in ("httpcore", "httpx", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
