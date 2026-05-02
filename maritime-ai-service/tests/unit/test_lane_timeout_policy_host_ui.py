from app.engine.multi_agent.lane_timeout_policy import (
    resolve_direct_lane_timeout_policy_impl,
)


def _host_ui_state():
    return {"routing_metadata": {"intent": "host_ui_navigation"}}


def test_host_ui_navigation_gets_provider_agnostic_first_token_sla():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="nvidia",
        query="Wiii oi, nut Kham pha khoa hoc o dau?",
        state=_host_ui_state(),
        is_identity_turn=False,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert policy.timeout_profile == "structured"
    assert policy.primary_timeout == 8.0
    assert policy.reason == "host_ui_navigation"


def test_host_ui_navigation_sla_still_applies_when_host_tools_are_bound():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="nvidia",
        query="Wiii oi, highlight nut Kham pha giup toi",
        state=_host_ui_state(),
        is_identity_turn=False,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=True,
    )

    assert policy.timeout_profile == "structured"
    assert policy.primary_timeout == 8.0
    assert policy.reason == "host_ui_navigation"


def test_non_host_ui_nvidia_turn_keeps_default_policy():
    policy = resolve_direct_lane_timeout_policy_impl(
        provider_name="nvidia",
        query="giai thich khoa hoc hang hai co ban",
        state={"routing_metadata": {"intent": "learning"}},
        is_identity_turn=False,
        is_short_house_chatter=False,
        use_house_voice_direct=False,
        tools_bound=False,
    )

    assert policy.timeout_profile is None
    assert policy.primary_timeout is None
    assert policy.reason == "provider_default"
