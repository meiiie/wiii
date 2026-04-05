"""Small helper utilities extracted from graph.py."""

from typing import Any, Optional

from app.engine.multi_agent.direct_reasoning import _infer_direct_reasoning_cue
from app.engine.multi_agent.code_studio_reasoning import _infer_code_studio_reasoning_cue
from app.engine.multi_agent.state import AgentState


def _direct_tool_names(items: list[dict] | None) -> list[str]:
    """Extract distinct tool names from tool usage payloads."""
    names: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        name = ""
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        elif item:
            name = str(item).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _extract_runtime_target(source_obj: Any | None) -> tuple[str | None, str | None]:
    provider_name = getattr(source_obj, "_wiii_provider_name", None) if source_obj is not None else None
    model_name = None
    if source_obj is not None:
        for attr_name in ("_wiii_model_name", "model_name", "model"):
            value = getattr(source_obj, attr_name, None)
            if isinstance(value, str) and value.strip():
                model_name = value.strip()
                break
    normalized_provider = (
        str(provider_name).strip().lower()
        if isinstance(provider_name, str) and provider_name.strip()
        else None
    )
    return normalized_provider, model_name


def _remember_runtime_target(
    state: Optional[AgentState],
    source_obj: Any | None,
) -> tuple[str | None, str | None]:
    provider_name, model_name = _extract_runtime_target(source_obj)
    if isinstance(state, dict):
        if provider_name and provider_name != "auto":
            state["_execution_provider"] = provider_name
        if model_name:
            state["_execution_model"] = model_name
            state["model"] = model_name
    return provider_name, model_name


def _copy_runtime_metadata(source_obj: Any | None, target_obj: Any | None):
    """Carry Wiii runtime metadata across LangChain wrapper/bind layers."""
    if source_obj is None or target_obj is None:
        return target_obj

    provider_name, model_name = _extract_runtime_target(source_obj)
    if provider_name:
        setattr(target_obj, "_wiii_provider_name", provider_name)
    if model_name:
        setattr(target_obj, "_wiii_model_name", model_name)

    tier_key = getattr(source_obj, "_wiii_tier_key", None)
    if isinstance(tier_key, str) and tier_key.strip():
        setattr(target_obj, "_wiii_tier_key", tier_key.strip().lower())

    requested_provider = getattr(source_obj, "_wiii_requested_provider", None)
    if isinstance(requested_provider, str) and requested_provider.strip():
        setattr(target_obj, "_wiii_requested_provider", requested_provider.strip().lower())

    return target_obj


def _infer_reasoning_cue(
    node_name: str,
    query: str,
    state: AgentState,
    tool_names: list[str] | None = None,
) -> str:
    """Resolve reasoning cue per capability node."""
    if node_name == "code_studio_agent":
        return _infer_code_studio_reasoning_cue(query, tool_names)
    return _infer_direct_reasoning_cue(query, state, tool_names)


def _node_style_prefix(node_name: str) -> str:
    """Map graph node name to narrator style prefix."""
    if node_name == "code_studio_agent":
        return "code-studio"
    return node_name


def _should_surface_direct_thinking(thinking: str) -> bool:
    """Direct chat should not expose raw chain-of-thought in the user UI."""
    return False


def _get_phase_fallback(state: AgentState) -> str:
    """Sprint 203: Context-appropriate fallback based on conversation phase."""
    phase = state.get("context", {}).get("conversation_phase", "opening")
    fallbacks = {
        "opening": "Mình là Wiii! Bạn muốn tìm hiểu gì hôm nay?",
        "engaged": "Hmm, mình gặp chút trục trặc khi xử lý. Bạn thử hỏi lại nhé?",
        "deep": "Xin lỗi, mình chưa xử lý được câu này. Bạn diễn đạt cách khác giúp mình nhé~",
        "closing": "Mình chưa hiểu rõ lắm. Bạn hỏi cụ thể hơn được không?",
    }
    return fallbacks.get(phase, fallbacks["engaged"])
