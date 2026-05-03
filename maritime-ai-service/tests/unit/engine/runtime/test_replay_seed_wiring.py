"""Phase 11c — verify replay seed flows from ContextVar into LLM api_kwargs.

The propagation channel itself is covered by ``test_replay_context``;
this file pins the integration: when a turn is wrapped in
``replay_seed_scope``, ``WiiiChatModel._build_api_kwargs`` must include
``seed`` for OpenAI-compat providers.
"""

from __future__ import annotations

from app.engine.llm_providers.wiii_chat_model import WiiiChatModel
from app.engine.runtime.replay_context import replay_seed_scope


def _build_model(base_url: str = "https://api.openai.com/v1") -> WiiiChatModel:
    return WiiiChatModel(
        model="gpt-4o-mini",
        api_key="test-key",
        base_url=base_url,
        temperature=0.0,
    )


def test_no_seed_when_not_in_scope():
    model = _build_model()
    api_kwargs = model._build_api_kwargs(
        messages=[{"role": "user", "content": "hi"}], kwargs={}
    )
    assert "seed" not in api_kwargs


def test_seed_injected_when_replay_scope_active():
    model = _build_model()
    with replay_seed_scope("12345"):
        api_kwargs = model._build_api_kwargs(
            messages=[{"role": "user", "content": "hi"}], kwargs={}
        )
    assert api_kwargs["seed"] == 12345


def test_seed_skipped_when_value_is_unparseable():
    model = _build_model()
    with replay_seed_scope("not-a-number"):
        api_kwargs = model._build_api_kwargs(
            messages=[{"role": "user", "content": "hi"}], kwargs={}
        )
    assert "seed" not in api_kwargs


def test_seed_dropped_for_zhipu_endpoint():
    """Zhipu's allowed-params filter strips ``seed`` — provider compat."""
    model = _build_model(base_url="https://open.bigmodel.cn/api/paas/v4")
    with replay_seed_scope("99"):
        api_kwargs = model._build_api_kwargs(
            messages=[{"role": "user", "content": "hi"}], kwargs={}
        )
    assert "seed" not in api_kwargs


def test_seed_passes_through_for_streaming_path():
    """The streaming path uses the same _build_api_kwargs — verify."""
    model = _build_model()
    with replay_seed_scope("77"):
        api_kwargs = model._build_api_kwargs(
            messages=[{"role": "user", "content": "hi"}], kwargs={}, stream=True
        )
    assert api_kwargs["seed"] == 77
    assert api_kwargs["stream"] is True
