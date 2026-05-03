"""Edge protocol adapters: wire-shape → ``TurnRequest``.

Phase 4 of the runtime migration epic (issue #207). Each adapter
normalises a different incoming wire format into the canonical
``TurnRequest`` so internal services see one shape regardless of which
endpoint was hit.
"""

from .openai_compat import openai_chat_completions_to_turn_request
from .wiii_native import wiii_chat_request_to_turn_request

__all__ = [
    "wiii_chat_request_to_turn_request",
    "openai_chat_completions_to_turn_request",
]
