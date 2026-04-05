from app.engine.multi_agent.direct_reasoning import (
    _build_direct_analytical_axes,
    _build_direct_evidence_plan,
    _infer_direct_thinking_mode,
    _infer_direct_topic_hint,
)


def test_direct_reasoning_infers_market_analysis_mode_for_oil_query():
    query = "phân tích giá dầu brent và tác động của OPEC+"

    mode = _infer_direct_thinking_mode(query, {}, ["tool_web_search"])
    topic = _infer_direct_topic_hint(query, {}, ["tool_web_search"])
    axes = _build_direct_analytical_axes(query, {}, ["tool_web_search"])
    plan = _build_direct_evidence_plan(query, {}, ["tool_web_search"])

    assert mode == "analytical_market"
    assert topic == "giá dầu"
    assert any("OPEC+" in axis for axis in axes)
    assert plan


def test_direct_reasoning_infers_math_analysis_mode_for_pendulum_query():
    query = "Phân tích về toán học con lắc đơn"

    mode = _infer_direct_thinking_mode(query, {}, [])
    topic = _infer_direct_topic_hint(query, {}, [])
    axes = _build_direct_analytical_axes(query, {}, [])
    plan = _build_direct_evidence_plan(query, {}, [])

    assert mode == "analytical_math"
    assert topic == "con lắc đơn"
    assert any("góc nhỏ" in axis for axis in axes)
    assert plan


def test_direct_reasoning_keeps_hard_math_generic_when_not_pendulum():
    query = (
        "Trình bày cách dùng spectral theorem, Stone theorem, và deficiency indices "
        "để phân tích self-adjoint operator trên Hilbert space có compact resolvent"
    )

    mode = _infer_direct_thinking_mode(query, {}, [])
    topic = _infer_direct_topic_hint(query, {}, [])
    axes = _build_direct_analytical_axes(query, {}, [])
    plan = _build_direct_evidence_plan(query, {}, [])

    assert mode == "analytical_math"
    assert topic == "bài toán toán tử trên không gian Hilbert"
    assert all("góc nhỏ" not in axis for axis in axes)
    assert any("điều kiện áp dụng" in axis for axis in axes)
    assert all("con lắc" not in step for step in plan)
