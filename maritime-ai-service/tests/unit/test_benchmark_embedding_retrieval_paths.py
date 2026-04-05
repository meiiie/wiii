from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import importlib.util
import sys


def _load_benchmark_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "benchmark_embedding_retrieval_paths.py"
    spec = importlib.util.spec_from_file_location("benchmark_embedding_retrieval_paths", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_snapshot_and_restore_runtime_settings_include_base_urls():
    module = _load_benchmark_module()

    settings_obj = SimpleNamespace(
        embedding_provider="auto",
        embedding_failover_chain=["ollama", "openai", "google"],
        embedding_model="embeddinggemma",
        embedding_dimensions=768,
        ollama_base_url="http://localhost:11434",
        openai_base_url="https://api.openai.com/v1",
        refresh_nested_views=lambda: None,
    )

    with patch.object(module, "settings", settings_obj), patch.object(
        module, "reset_embedding_backend"
    ) as reset_backend, patch.object(
        module, "invalidate_embedding_selectability_cache"
    ) as invalidate_cache:
        snapshot = module._snapshot_runtime_settings()
        settings_obj.embedding_provider = "google"
        settings_obj.embedding_failover_chain = ["google"]
        settings_obj.embedding_model = "models/gemini-embedding-001"
        settings_obj.embedding_dimensions = 1536
        settings_obj.ollama_base_url = "http://host.docker.internal:11434"
        settings_obj.openai_base_url = "https://openrouter.ai/api/v1"

        module._restore_runtime_settings(snapshot)

    assert settings_obj.embedding_provider == "auto"
    assert settings_obj.embedding_failover_chain == ["ollama", "openai", "google"]
    assert settings_obj.embedding_model == "embeddinggemma"
    assert settings_obj.embedding_dimensions == 768
    assert settings_obj.ollama_base_url == "http://localhost:11434"
    assert settings_obj.openai_base_url == "https://api.openai.com/v1"
    reset_backend.assert_called_once()
    invalidate_cache.assert_called_once()


def test_restore_persisted_runtime_policy_resets_embedding_caches():
    module = _load_benchmark_module()

    with patch.object(
        module,
        "apply_persisted_llm_runtime_policy",
        return_value=SimpleNamespace(payload={"embedding_provider": "auto"}),
    ), patch.object(module, "reset_embedding_backend") as reset_backend, patch.object(
        module, "invalidate_embedding_selectability_cache"
    ) as invalidate_cache:
        restored = module._restore_persisted_runtime_policy()

    assert restored is True
    reset_backend.assert_called_once()
    invalidate_cache.assert_called_once()
