from app.engine import llm_runtime_state


def test_runtime_state_bootstraps_llm_pool_access_lazily(monkeypatch):
    llm_runtime_state._get_stats = None
    llm_runtime_state._get_provider_info = None
    llm_runtime_state._get_request_selectable_providers = None

    def _fake_import(_name: str):
        llm_runtime_state.register_llm_runtime_access(
            get_stats=lambda: {"active_provider": "zhipu"},
            get_provider_info=lambda provider: {"provider": provider},
            get_request_selectable_providers=lambda: ["zhipu"],
        )
        return object()

    monkeypatch.setattr(llm_runtime_state.importlib, "import_module", _fake_import)

    assert llm_runtime_state.get_llm_runtime_stats() == {"active_provider": "zhipu"}
    assert llm_runtime_state.get_llm_runtime_provider_info("zhipu") == {"provider": "zhipu"}
    assert llm_runtime_state.get_llm_runtime_request_selectable_providers() == ["zhipu"]
