"""
Sentry Error Tracking Configuration.
Production Hardening — March 2026.

References:
- Sentry FastAPI Integration (2026): auto-enables FastApiIntegration
- enable_logs=True: forwards Python logging to Sentry Logs product (new 2025)
- before_send_transaction: filter noisy health checks
"""
import logging

logger = logging.getLogger(__name__)

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]


def init_sentry(
    dsn: str,
    environment: str = "production",
    traces_sample_rate: float = 0.2,
) -> None:
    """Initialize Sentry SDK for FastAPI.

    Args:
        dsn: Sentry DSN. Empty string disables Sentry.
        environment: Environment tag (production/staging/development).
        traces_sample_rate: Fraction of transactions to trace (0.0-1.0).
    """
    if not dsn:
        logger.info("Sentry DSN not configured — error tracking disabled")
        return

    if sentry_sdk is None:
        logger.warning("sentry-sdk not installed — error tracking disabled. pip install sentry-sdk[fastapi]")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        before_send=_before_send,
        before_send_transaction=_before_send_transaction,
    )
    logger.info("Sentry initialized (env=%s, traces=%.0f%%)", environment, traces_sample_rate * 100)


def _before_send(event: dict, hint: dict) -> dict | None:
    """Filter events before sending to Sentry.

    - Drop 404s (not real errors)
    - Drop expected exceptions (KeyboardInterrupt, ConnectionResetError)
    - Scrub sensitive headers (API keys, auth tokens)
    """
    if "exc_info" in hint:
        exc_type = hint["exc_info"][0]
        if exc_type in (KeyboardInterrupt, SystemExit, ConnectionResetError):
            return None
        exc = hint["exc_info"][1]
        if hasattr(exc, "status_code") and exc.status_code == 404:
            return None

    # Scrub sensitive headers (case-insensitive)
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        sensitive_keys = {"x-api-key", "authorization", "cookie"}
        for key in list(headers.keys()):
            if key.lower() in sensitive_keys:
                headers[key] = "[Filtered]"

    return event


def _before_send_transaction(event: dict, hint: dict) -> dict | None:
    """Drop noisy health-check transactions."""
    url = event.get("request", {}).get("url", "")
    if any(path in url for path in ("/health", "/readyz", "/livez", "/metrics")):
        return None
    return event
