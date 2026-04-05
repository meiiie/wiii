import json
from typing import Any, Callable


def parse_visual_payloads_impl(
    raw: Any,
    *,
    payload_class: type,
    build_multi_figure_payloads: Callable[..., list[Any]],
    coerce_visual_payload_data: Callable[[dict[str, Any]], dict[str, Any]],
    validation_error_cls: type[Exception],
) -> list[Any]:
    if isinstance(raw, payload_class):
        return [raw]

    if isinstance(raw, list):
        payloads: list[Any] = []
        for item in raw:
            payloads.extend(
                parse_visual_payloads_impl(
                    item,
                    payload_class=payload_class,
                    build_multi_figure_payloads=build_multi_figure_payloads,
                    coerce_visual_payload_data=coerce_visual_payload_data,
                    validation_error_cls=validation_error_cls,
                )
            )
        return payloads

    if isinstance(raw, dict):
        if isinstance(raw.get("figures"), list):
            payloads = build_multi_figure_payloads(
                default_visual_type=str(raw.get("type") or raw.get("visual_type") or "comparison"),
                raw_group=raw,
            )
            if payloads:
                return payloads
        try:
            return [payload_class.model_validate(coerce_visual_payload_data(raw))]
        except validation_error_cls:
            return []

    if not raw:
        return []

    text = str(raw).strip()
    if not text:
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    return parse_visual_payloads_impl(
        data,
        payload_class=payload_class,
        build_multi_figure_payloads=build_multi_figure_payloads,
        coerce_visual_payload_data=coerce_visual_payload_data,
        validation_error_cls=validation_error_cls,
    )


def parse_visual_payload_impl(
    raw: Any,
    *,
    parse_visual_payloads: Callable[[Any], list[Any]],
) -> Any | None:
    payloads = parse_visual_payloads(raw)
    return payloads[0] if payloads else None
