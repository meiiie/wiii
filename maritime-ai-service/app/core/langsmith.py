"""
LangSmith Observability Integration (Sprint 144b)

Sets LANGCHAIN_TRACING_V2 environment variables at startup so that
LangChain/LangGraph automatically traces every LLM call, tool invocation,
and graph node to the LangSmith dashboard.

Three public functions:
  - configure_langsmith(settings)  — called once at app startup
  - is_langsmith_enabled()         — boolean check
  - get_langsmith_callback(...)    — per-request callback with metadata tags
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_langsmith_enabled: bool = False


def configure_langsmith(settings: Any) -> None:
    """
    Set LangChain tracing environment variables from app settings.

    Must be called BEFORE LLM Pool initialization so that LangChain
    picks up the env vars when constructing providers.

    Args:
        settings: Pydantic Settings instance with langsmith_* fields.
    """
    global _langsmith_enabled

    if not settings.enable_langsmith:
        logger.debug("[LANGSMITH] Disabled via config")
        return

    api_key = settings.langsmith_api_key
    if not api_key:
        logger.warning(
            "[LANGSMITH] enable_langsmith=True but langsmith_api_key is empty. "
            "Tracing will NOT be activated."
        )
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint

    _langsmith_enabled = True
    logger.info(
        "[LANGSMITH] Tracing enabled — project=%s, endpoint=%s",
        settings.langsmith_project,
        settings.langsmith_endpoint,
    )


def is_langsmith_enabled() -> bool:
    """Return True if LangSmith tracing was successfully configured."""
    return _langsmith_enabled


def get_langsmith_callback(
    user_id: str = "",
    session_id: str = "",
    domain_id: str = "",
    model_provider: str = "",
) -> Optional[Any]:
    """
    Create a per-request LangChainTracer callback with metadata tags.

    Tags enable filtering in the LangSmith dashboard by user, session,
    and domain.  Returns None when LangSmith is disabled or if the
    langsmith SDK is not installed.

    Args:
        user_id: User identifier for dashboard filtering.
        session_id: Session identifier.
        domain_id: Domain plugin ID.

    Returns:
        LangChainTracer instance or None.
    """
    if not _langsmith_enabled:
        return None

    try:
        from langsmith import Client
        from langchain_core.tracers import LangChainTracer

        tags = []
        if domain_id:
            tags.append(f"domain:{domain_id}")
        if user_id:
            tags.append(f"user:{user_id}")

        metadata = {}
        if user_id:
            metadata["user_id"] = user_id
        if session_id:
            metadata["session_id"] = session_id
        if domain_id:
            metadata["domain_id"] = domain_id
        if model_provider:
            metadata["model_provider"] = model_provider

        client = Client()
        return LangChainTracer(
            client=client,
            project_name=os.environ.get("LANGCHAIN_PROJECT", "wiii"),
            tags=tags,
            extra={"metadata": metadata} if metadata else None,
        )
    except ImportError:
        logger.debug("[LANGSMITH] langsmith or langchain_core.tracers not installed")
        return None
    except Exception as e:
        logger.warning("[LANGSMITH] Failed to create callback: %s", e)
        return None
