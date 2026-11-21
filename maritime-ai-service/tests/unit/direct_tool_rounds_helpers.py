from types import SimpleNamespace


def _state_with_targets(*ids: str) -> SimpleNamespace:
    """Build minimal state.host_context.page.metadata.available_targets."""
    return SimpleNamespace(
        host_context={
            "page": {
                "metadata": {
                    "available_targets": [{"id": i} for i in ids],
                }
            }
        }
    )
