"""LangSmith observability integration — runtime-migration-aware stub.

History: this module wired ``langchain_core.tracers.LangChainTracer`` into
every LLM call so traces showed up in the LangSmith dashboard. Phase 7 of
the runtime migration epic (#207) drops the LangChain-tracer dependency
because Wiii no longer routes through ``BaseChatModel`` callbacks.

The ``langsmith`` SDK itself stays a top-level dep — it is independent of
``langchain-core`` and supports direct trace posting. A future PR can
restore observability by calling ``langsmith.Client`` from a runtime hook
that wraps ``UnifiedLLMClient`` invocations. Until that lands, this
module keeps the public surface (``configure_langsmith`` /
``is_langsmith_enabled`` / ``get_langsmith_callback``) so call sites do
not need to branch — every callback request just returns ``None``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_langsmith_enabled: bool = False


def configure_langsmith(settings: Any) -> None:
    """Capture intent — actual tracing wiring lives in the future direct hook.

    Reads ``settings.enable_langsmith`` for a debug log only; sets no env
    vars now that the LangChain auto-tracer has been removed.
    """
    global _langsmith_enabled

    if not getattr(settings, "enable_langsmith", False):
        logger.debug("[LANGSMITH] Disabled via config")
        return

    api_key = getattr(settings, "langsmith_api_key", "")
    if not api_key:
        logger.warning(
            "[LANGSMITH] enable_langsmith=True but langsmith_api_key is empty."
        )
        return

    _langsmith_enabled = True
    logger.info(
        "[LANGSMITH] Flag enabled (project=%s) — tracing will be wired by a "
        "follow-up direct integration; LangChain auto-tracer was removed in "
        "the runtime-migration epic (#207).",
        getattr(settings, "langsmith_project", "wiii"),
    )


def is_langsmith_enabled() -> bool:
    """Return True if the flag was honoured and an API key was supplied."""
    return _langsmith_enabled


def get_langsmith_callback(
    user_id: str = "",
    session_id: str = "",
    domain_id: str = "",
    model_provider: str = "",
) -> Optional[Any]:
    """Always returns ``None`` — see module docstring.

    Kept as a stable surface so hot paths can call it unconditionally.
    """
    return None
