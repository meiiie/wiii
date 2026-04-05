"""
Service layer for Wiii.

Sprint 140: Lazy imports to break circular dependency chain
(graph → tutor_node → output_processor → services/__init__ → chat_service → graph).
"""

__all__ = [
    "ChatService",
    "get_chat_service",
    "reset_chat_service",
    "ChatResponseBuilder",
    "FormattedResponse",
    "get_chat_response_builder",
]

_ATTR_MAP = {
    "ChatService": ("app.services.chat_service", "ChatService"),
    "get_chat_service": ("app.services.chat_service", "get_chat_service"),
    "reset_chat_service": ("app.services.chat_service", "reset_chat_service"),
    "ChatResponseBuilder": ("app.services.chat_response_builder", "ChatResponseBuilder"),
    "FormattedResponse": ("app.services.chat_response_builder", "FormattedResponse"),
    "get_chat_response_builder": ("app.services.chat_response_builder", "get_chat_response_builder"),
}


def __getattr__(name: str):
    if name in _ATTR_MAP:
        module_path, attr_name = _ATTR_MAP[name]
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    try:
        import importlib

        return importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as exc:
        if exc.name != f"{__name__}.{name}":
            raise
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
