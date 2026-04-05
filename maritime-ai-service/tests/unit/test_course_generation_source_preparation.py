from types import SimpleNamespace

import pytest

import app.engine.workflows.course_generation_source_preparation as prep


def _build_markdown(section_count: int = 4, repeat: int = 120) -> str:
    sections: list[str] = []
    for index in range(1, section_count + 1):
        body = ("Noi dung chi tiet ve phan %d. " % index) * repeat
        sections.append(
            f"<!-- page {index} -->\n# Chuong {index}\n{body}\n- Y chinh {index}\n- Vi du {index}"
        )
    return "\n\n".join(sections)


def test_prepare_outline_source_keeps_small_markdown(monkeypatch):
    monkeypatch.setattr(prep, "_resolve_candidate_providers", lambda **_: ("google",))

    result = prep.prepare_outline_source(markdown="# Chuong 1\nNoi dung ngan", tier="deep")

    assert result.mode == "full"
    assert result.rendered_markdown.startswith("# Chuong 1")
    assert result.candidate_providers == ("google",)


def test_resolve_candidate_providers_prefers_runtime_route(monkeypatch):
    monkeypatch.setattr(
        prep.LLMPool,
        "resolve_runtime_route",
        lambda provider, tier, failover_mode=None: SimpleNamespace(
            provider="google",
            fallback_provider="zhipu",
        ),
    )

    providers = prep._resolve_candidate_providers(
        provider=None,
        failover_mode=prep.FAILOVER_MODE_AUTO,
        tier="deep",
    )

    assert providers == ("google", "zhipu")


def test_prepare_outline_source_compacts_large_markdown(monkeypatch):
    monkeypatch.setattr(prep, "_resolve_candidate_providers", lambda **_: ("google", "zhipu"))
    monkeypatch.setattr(prep, "_resolve_source_budget_tokens", lambda providers, *, tier: 700)

    result = prep.prepare_outline_source(markdown=_build_markdown(section_count=4), tier="deep")

    assert result.mode == "chunk_compact"
    assert result.prepared_tokens_estimate <= result.token_budget
    assert "[PREPARED_DOCUMENT_MAP]" in result.rendered_markdown
    assert "pages 1-1" in result.rendered_markdown


def test_prepare_outline_source_falls_back_to_heading_index(monkeypatch):
    monkeypatch.setattr(prep, "_resolve_candidate_providers", lambda **_: ("zhipu",))
    monkeypatch.setattr(prep, "_resolve_source_budget_tokens", lambda providers, *, tier: 30)

    result = prep.prepare_outline_source(markdown=_build_markdown(section_count=8, repeat=180), tier="deep")

    assert result.mode == "heading_index"
    assert result.prepared_tokens_estimate <= result.token_budget
    assert "mode=heading_index" in result.rendered_markdown
