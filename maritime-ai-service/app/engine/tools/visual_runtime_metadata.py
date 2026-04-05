"""Runtime metadata helper implementations for structured visual generation."""

from typing import Any

def _get_runtime_visual_metadata_impl(get_runtime_context) -> dict[str, Any]:
    runtime = get_runtime_context()
    if runtime and isinstance(runtime.metadata, dict):
        return runtime.metadata
    return {}


def _runtime_metadata_text_impl(key: str, default: str, get_runtime_metadata) -> str:
    value = get_runtime_metadata().get(key, default)
    return str(value or default).strip()


def _runtime_metadata_int_impl(key: str, default: int, get_runtime_metadata) -> int:
    value = get_runtime_metadata().get(key, default)
    try:
        return int(value)
    except Exception:
        return default


def _runtime_presentation_intent_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("presentation_intent", "text")


def _runtime_renderer_contract_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("renderer_contract", "")


def _runtime_quality_profile_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("quality_profile", "standard")


def _runtime_studio_lane_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("studio_lane", "")


def _runtime_artifact_kind_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("artifact_kind", "")


def _runtime_code_studio_version_impl(get_runtime_metadata_int) -> int:
    return max(0, get_runtime_metadata_int("code_studio_version", 0))


def _runtime_visual_user_query_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("visual_user_query", "")


def _runtime_preferred_render_surface_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("preferred_render_surface", "")


def _runtime_planning_profile_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("planning_profile", "")


def _runtime_thinking_floor_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("thinking_floor", "")


def _runtime_critic_policy_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("critic_policy", "")


def _runtime_living_expression_mode_impl(get_runtime_metadata_text) -> str:
    return get_runtime_metadata_text("living_expression_mode", "")


def _metadata_text_impl(metadata: dict[str, Any] | None, key: str, default: str = "") -> str:
    if not isinstance(metadata, dict):
        return default
    value = metadata.get(key, default)
    return str(value or default).strip()
