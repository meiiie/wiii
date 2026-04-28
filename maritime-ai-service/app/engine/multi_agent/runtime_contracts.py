"""Native Wiii runtime contracts behind legacy-compatible entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class WiiiRunContext:
    """Stable runtime context shared by sync and streaming Wiii turns."""

    user_id: str
    session_id: str = ""
    domain_id: str | None = None
    organization_id: str | None = None
    context: Mapping[str, Any] | None = None
    thinking_effort: str | None = None
    provider: str | None = None
    model: str | None = None

    def context_dict(self) -> dict[str, Any]:
        """Return a mutable context copy for the active runtime adapter."""

        ctx = dict(self.context or {})
        if self.organization_id and not ctx.get("organization_id"):
            ctx["organization_id"] = self.organization_id
        return ctx


@dataclass(frozen=True)
class WiiiTurnRequest:
    """One user turn entering the WiiiRunner runtime."""

    query: str
    run_context: WiiiRunContext

    def to_runtime_kwargs(self) -> dict[str, Any]:
        """Adapt native Wiii request shape to the current runtime function."""

        return {
            "query": self.query,
            "user_id": self.run_context.user_id,
            "session_id": self.run_context.session_id,
            "context": self.run_context.context_dict(),
            "domain_id": self.run_context.domain_id,
            "thinking_effort": self.run_context.thinking_effort,
            "provider": self.run_context.provider,
            "model": self.run_context.model,
        }


@dataclass(frozen=True)
class WiiiTurnState:
    """Typed view over WiiiRunner state snapshots."""

    values: Mapping[str, Any]

    @property
    def final_response(self) -> str:
        return str(self.values.get("final_response") or self.values.get("response") or "")

    @property
    def current_agent(self) -> str:
        return str(self.values.get("current_agent") or "")

    @property
    def provider(self) -> str | None:
        provider = self.values.get("_execution_provider") or self.values.get("provider")
        return str(provider) if provider else None

    @property
    def model(self) -> str | None:
        model = self.values.get("_execution_model") or self.values.get("model")
        return str(model) if model else None


@dataclass(frozen=True)
class WiiiTurnResult:
    """Result payload returned by a completed Wiii turn."""

    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> "WiiiTurnResult":
        return cls(payload=dict(payload or {}))

    @property
    def response(self) -> str:
        return str(self.payload.get("response") or "")

    @property
    def current_agent(self) -> str:
        return str(self.payload.get("current_agent") or "")

    @property
    def error(self) -> Any:
        return self.payload.get("error")

    @property
    def provider(self) -> str | None:
        provider = self.payload.get("_execution_provider") or self.payload.get("provider")
        return str(provider) if provider else None

    @property
    def model(self) -> str | None:
        model = self.payload.get("_execution_model") or self.payload.get("model")
        return str(model) if model else None


@dataclass(frozen=True)
class WiiiStreamEvent:
    """Typed wrapper for the existing SSE-compatible stream tuple."""

    event_type: str
    payload: Any = None
    raw_event: Any = None

    @classmethod
    def from_legacy_tuple(cls, event: Any) -> "WiiiStreamEvent":
        if isinstance(event, cls):
            return event
        if hasattr(event, "type") and hasattr(event, "content"):
            return cls(
                event_type=str(event.type),
                payload=getattr(event, "content", None),
                raw_event=event,
            )
        if isinstance(event, tuple) and event:
            payload = event[1] if len(event) > 1 else None
            return cls(event_type=str(event[0]), payload=payload)
        return cls(event_type="unknown", payload=event)

    def to_legacy_tuple(self) -> tuple[str, Any]:
        return (self.event_type, self.payload)

    @property
    def node_name(self) -> str:
        if self.event_type != "graph" or not isinstance(self.payload, dict):
            return ""
        return str(next(iter(self.payload), ""))

    @property
    def type(self) -> str:
        return self.event_type

    @property
    def content(self) -> Any:
        return getattr(self.raw_event, "content", self.payload)

    @property
    def node(self) -> str | None:
        return getattr(self.raw_event, "node", None)

    @property
    def step(self) -> str | None:
        return getattr(self.raw_event, "step", None)

    @property
    def confidence(self) -> float | None:
        return getattr(self.raw_event, "confidence", None)

    @property
    def details(self) -> dict[str, Any] | None:
        return getattr(self.raw_event, "details", None)

    @property
    def subtype(self) -> str | None:
        return getattr(self.raw_event, "subtype", None)


__all__ = [
    "WiiiRunContext",
    "WiiiStreamEvent",
    "WiiiTurnRequest",
    "WiiiTurnResult",
    "WiiiTurnState",
]
