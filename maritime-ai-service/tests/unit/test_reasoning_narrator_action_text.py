def test_reasoning_narrator_action_text_avoids_doi_chieu_duplication_with_vietnamese_text():
    from app.engine.reasoning.reasoning_narrator import (
        ReasoningNarrator,
        ReasoningRenderRequest,
    )

    narrator = ReasoningNarrator()
    result = narrator.render_fast(
        ReasoningRenderRequest(
            node="direct",
            phase="act",
            user_goal="ph\u00e2n t\u00edch gi\u00e1 d\u1ea7u",
            thinking_mode="analytical_market",
            evidence_plan=[
                "\u0111\u1ed1i chi\u1ebfu Brent v\u00e0 WTI",
                "t\u00e1ch OPEC+ kh\u1ecfi y\u1ebfu t\u1ed1 nhu c\u1ea7u",
            ],
        )
    )

    lowered = result.action_text.lower()
    assert "\u0111\u1ed1i chi\u1ebfu \u0111\u1ed1i chi\u1ebfu" not in lowered
    assert "doi chieu doi chieu" not in lowered
    assert "brent" in lowered
