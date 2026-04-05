"""Model-switch prompt helpers for runtime failover and provider outages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.llm_selectability_service import get_llm_selectability_snapshot

_REASON_TEXT: dict[str, str] = {
    "rate_limit": "dang cham gioi han hoac quota",
    "busy": "dang cham gioi han hoac quota",
    "auth_error": "dang gap loi xac thuc",
    "provider_unavailable": "tam thoi khong kha dung",
    "host_down": "hien chua san sang",
    "server_error": "dang gap loi may chu",
    "timeout": "phan hoi qua lau",
    "verifying": "dang duoc he thong xac minh",
}

_PROVIDER_LABELS: dict[str, str] = {
    "google": "Gemini",
    "zhipu": "Zhipu GLM",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
}


def _normalize_provider(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _normalize_reason_code(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text == "busy":
        return "rate_limit"
    return text


def _provider_label(provider: str | None) -> str | None:
    if not provider:
        return None
    return _PROVIDER_LABELS.get(provider, provider.title())


def _build_options(
    *,
    current_provider: str | None,
    preferred_provider: str | None = None,
) -> list[dict[str, Any]]:
    current = _normalize_provider(current_provider)
    preferred = _normalize_provider(preferred_provider)
    selectable = [
        (index, item)
        for index, item in enumerate(get_llm_selectability_snapshot())
        if item.state == "selectable" and item.provider != current
    ]

    def _sort_key(entry) -> tuple[int, int]:
        index, item = entry
        return (0 if preferred and item.provider == preferred else 1, index)

    selectable.sort(key=_sort_key)
    options: list[dict[str, Any]] = []
    for _, item in selectable[:3]:
        options.append(
            {
                "provider": item.provider,
                "label": item.display_name,
                "selected_model": item.selected_model,
            }
        )
    return options


def build_model_switch_prompt_for_unavailable(
    *,
    provider: str | None,
    reason_code: str | None,
) -> dict[str, Any] | None:
    current_provider = _normalize_provider(provider)
    normalized_reason = _normalize_reason_code(reason_code) or "provider_unavailable"
    options = _build_options(current_provider=current_provider)
    if not options:
        return None

    current_label = _provider_label(current_provider) or "Model hien tai"
    recommended = options[0]
    reason_text = _REASON_TEXT.get(normalized_reason, "tam thoi chua san sang")
    recommended_label = recommended["label"]
    recommended_model = recommended.get("selected_model")
    model_suffix = f" ({recommended_model})" if recommended_model else ""

    return {
        "trigger": "provider_unavailable",
        "reason_code": normalized_reason,
        "current_provider": current_provider,
        "title": "Doi model de tiep tuc?",
        "message": (
            f"{current_label} {reason_text}. "
            f"Ban co the thu {recommended_label}{model_suffix} cho luot nay "
            "hoac chuyen han cho cac luot sau."
        ),
        "recommended_provider": recommended["provider"],
        "options": options,
        "allow_retry_once": True,
        "allow_session_switch": True,
    }


def build_model_switch_prompt_for_failover(
    *,
    failover: Mapping[str, Any] | None,
    requested_provider: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(failover, Mapping):
        return None
    if not bool(failover.get("switched")):
        return None

    initial_provider = _normalize_provider(
        failover.get("initial_provider") or requested_provider
    )
    final_provider = _normalize_provider(failover.get("final_provider"))
    if not initial_provider or not final_provider or initial_provider == final_provider:
        return None

    normalized_reason = _normalize_reason_code(
        failover.get("last_reason_category") or failover.get("last_reason_code")
    ) or "provider_unavailable"
    options = _build_options(
        current_provider=initial_provider,
        preferred_provider=final_provider,
    )
    if not options:
        return None

    preferred_option = next(
        (item for item in options if item["provider"] == final_provider),
        options[0],
    )
    initial_label = _provider_label(initial_provider) or "model cu"
    final_label = preferred_option["label"]
    final_model = preferred_option.get("selected_model")
    model_suffix = f" ({final_model})" if final_model else ""
    reason_text = _REASON_TEXT.get(normalized_reason, "dang gap van de")

    return {
        "trigger": "hard_failover",
        "reason_code": normalized_reason,
        "current_provider": initial_provider,
        "title": "Giu model moi cho cac luot sau?",
        "message": (
            f"Wiii da chuyen tu {initial_label} sang {final_label}{model_suffix} "
            f"vi {initial_label} {reason_text}. "
            f"Neu ban muon, minh co the giu {final_label} cho cac luot sau."
        ),
        "recommended_provider": preferred_option["provider"],
        "options": options,
        "allow_retry_once": False,
        "allow_session_switch": True,
    }
