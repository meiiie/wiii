"""Execution lane enum — borrowed from Unsloth pattern.

Resolved BEFORE provider selection. Routes do not need to know
implementation detail; lane switching stays behind a stable interface.

Phase 0: enum only (this file). Phase 4 will add the lane resolver
that maps a ``TurnRequest`` + ``RuntimeIntent`` to one of these values.
"""
from __future__ import annotations

from enum import Enum


class ExecutionLane(str, Enum):
    """Where a single turn actually executes.

    Each lane has different capability guarantees (streaming shape, tool
    support, structured-output reliability, vision support, latency
    profile). The runtime picks one lane, then resolves the concrete
    provider/model **inside** that lane — not the other way around.
    """

    CLOUD_NATIVE_SDK = "cloud_native_sdk"
    """Direct provider SDK (``anthropic``, ``openai``, ``google-genai``).

    Used when the turn needs provider-specific features (Anthropic
    extended thinking, OpenAI Realtime audio, Gemini grounding) that
    OpenAI-compatible HTTP cannot expose.
    """

    OPENAI_COMPATIBLE_HTTP = "openai_compatible_http"
    """``AsyncOpenAI`` against any OpenAI-compatible endpoint.

    Default lane for chat/completion calls. Backed by
    ``UnifiedLLMClient``. Wiii's main path post-Phase-3.
    """

    LOCAL_WORKER = "local_worker"
    """Local subprocess inference (Ollama, llama.cpp, sandboxed Python).

    Borrowed from Unsloth's worker-isolation pattern: incompatible
    dependency stacks (e.g. ``transformers`` major version conflicts)
    live in dedicated processes so the API host stays light.
    """

    TOOL_ORCHESTRATED = "tool_orchestrated"
    """Multi-step agent loop with tool calling.

    Used when the turn requires the agentic ReAct loop (browser agent,
    code studio, RAG with adaptive retrieval). Built on whichever cloud
    or compatible lane the underlying tier resolves to.
    """

    EMBEDDING = "embedding"
    """Embedding-only call (no chat completion).

    Vector store insertion, query embedding, semantic similarity. Lower
    latency budget; no tool dispatch overhead.
    """

    VISION_EXTRACTION = "vision_extraction"
    """Image/PDF extraction with vision-capable model.

    Different streaming shape and timeout profile than chat. Kept
    separate so capability checks do not have to special-case it.
    """
