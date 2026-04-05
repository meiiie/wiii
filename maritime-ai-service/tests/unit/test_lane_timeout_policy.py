import pytest

from app.engine.multi_agent.lane_timeout_policy import (
    resolve_direct_fallback_provider_allowlist_impl,
    resolve_direct_lane_timeout_policy_impl,
    resolve_product_curation_timeout_impl,
)


def test_zhipu_origin_turn_gets_structured_story_sla():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="zhipu",
        query="Wiii duoc sinh ra nhu the nao?",
        state={},
        is_identity_turn=True,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert policy.timeout_profile == "structured"
    assert policy.primary_timeout == pytest.approx(18.0)
    assert policy.reason == "zhipu_selfhood_story"


def test_zhipu_emotional_turn_gets_fast_structured_sla():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="zhipu",
        query="minh buon qua",
        state={},
        is_identity_turn=False,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert policy.timeout_profile == "structured"
    assert policy.primary_timeout == pytest.approx(8.0)
    assert policy.reason == "zhipu_emotional_support"


def test_zhipu_analytical_math_turn_gets_longer_first_chunk_sla():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="zhipu",
        query="Hay giai thich compact resolvent va spectral theorem tren khong gian Hilbert",
        state={},
        is_identity_turn=False,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert policy.timeout_profile is None
    assert policy.primary_timeout == pytest.approx(18.0)
    assert policy.reason == "zhipu_analytical_math"


def test_non_zhipu_direct_turn_keeps_default_policy():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="google",
        query="Wiii la ai?",
        state={},
        is_identity_turn=True,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert policy.timeout_profile is None
    assert policy.primary_timeout is None
    assert policy.reason == "provider_default"


def test_zhipu_selfhood_turn_prefers_ollama_as_only_cross_provider_fallback():
    allowlist = resolve_direct_fallback_provider_allowlist_impl(
        provider_name="zhipu",
        query="Wiii duoc sinh ra nhu the nao?",
        state={},
        is_identity_turn=True,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert allowlist == ("ollama",)


def test_noncritical_direct_turn_keeps_default_fallback_chain():
    allowlist = resolve_direct_fallback_provider_allowlist_impl(
        provider_name="zhipu",
        query="so sanh gia dau hien nay",
        state={},
        is_identity_turn=False,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert allowlist is None


def test_product_curation_timeout_tightens_for_zhipu_compare_turn():
    timeout_seconds = resolve_product_curation_timeout_impl(
        provider_name="zhipu",
        query="so sanh 3 lua chon tai nghe duoi 3 trieu",
        total_products=24,
        requested_timeout=None,
    )

    assert timeout_seconds == pytest.approx(8.0)


def test_product_curation_timeout_respects_explicit_request():
    timeout_seconds = resolve_product_curation_timeout_impl(
        provider_name="zhipu",
        query="tim tai nghe",
        total_products=8,
        requested_timeout=11.5,
    )

    assert timeout_seconds == pytest.approx(11.5)
