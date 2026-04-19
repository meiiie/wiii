"""Tests for AI slop detection (Phase 3)."""

import pytest

from app.engine.tools.visual_ai_slop import (
    SlopViolation,
    check_ai_slop_patterns,
    check_ai_slop_summary,
)


class TestCheckAiSlopPatterns:
    def test_clean_html_no_violations(self):
        html = "<html><body><h1>Hello</h1><p>Clean output</p></body></html>"
        violations = check_ai_slop_patterns(html)
        assert violations == []

    def test_gradient_overuse_detected(self):
        html = """
        <div style="background: linear-gradient(to right, #a, #b)"></div>
        <div style="background: linear-gradient(to right, #c, #d)"></div>
        <div style="background: linear-gradient(to right, #e, #f)"></div>
        <div style="background: linear-gradient(to right, #g, #h)"></div>
        """
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "gradient_overuse" in rules

    def test_gradient_exactly_three_no_violation(self):
        html = """
        <div style="background: linear-gradient(#a, #b)"></div>
        <div style="background: linear-gradient(#c, #d)"></div>
        <div style="background: linear-gradient(#e, #f)"></div>
        """
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "gradient_overuse" not in rules

    def test_emoji_spam_detected(self):
        # Use unicode escapes to avoid Windows cp1252 encoding issues
        html = "<p>" + "\U0001F680" * 6 + "</p>"  # 6 rocket emojis
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "emoji_spam" in rules

    def test_few_emoji_no_violation(self):
        html = "<p>One " + "\U0001F525" + " in text</p>"  # 1 fire emoji
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "emoji_spam" not in rules

    def test_ai_card_trope_detected(self):
        html = """
        <div style="border-left: 4px solid #D97757; border-radius: 12px;
                    background: linear-gradient(to right, #fff, #f5f5f5);">
          <h3>Feature</h3><p>Description</p>
        </div>
        """
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "ai_card_trope" in rules

    def test_banned_font_inter_detected(self):
        html = '<div style="font-family: Inter, sans-serif;">Text</div>'
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "banned_font" in rules

    def test_banned_font_roboto_detected(self):
        html = '<div style="font-family: Roboto">Text</div>'
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "banned_font" in rules

    def test_allowed_font_no_violation(self):
        html = '<div style="font-family: DM Sans, sans-serif;">Text</div>'
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "banned_font" not in rules

    def test_purple_gradient_hero_detected(self):
        html = """
        <div class="hero" style="background: linear-gradient(135deg, #7c3aed, #3b82f6);">
          <h1>Welcome</h1>
        </div>
        """
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "purple_gradient_hero" in rules

    def test_data_slop_detected(self):
        html = """
        <div class="stat-card">1</div>
        <div class="stat-card">2</div>
        <div class="stat-card">3</div>
        <div class="stat-card">4</div>
        <div class="stat-card">5</div>
        <div class="stat-card">6</div>
        <div class="stat-card">7</div>
        """
        violations = check_ai_slop_patterns(html)
        rules = [v.rule for v in violations]
        assert "data_slop" in rules


class TestSlopViolation:
    def test_violation_fields(self):
        v = SlopViolation(rule="test", severity="high", message="Test msg")
        assert v.rule == "test"
        assert v.severity == "high"
        assert v.message == "Test msg"


class TestCheckAiSlopSummary:
    def test_summary_groups_by_severity(self):
        html = (
            '<div style="background: linear-gradient(#a,#b); border-radius: 8px;'
            ' border-left: 3px solid blue;">'
            '<p style="font-family: Inter">' + "\U0001F680" * 6 + '</p>'
            '</div>'
            '<div style="background: linear-gradient(#c,#d)"></div>'
            '<div style="background: linear-gradient(#e,#f)"></div>'
            '<div style="background: linear-gradient(#g,#h)"></div>'
        )
        summary = check_ai_slop_summary(html)
        assert "high" in summary or "medium" in summary or "low" in summary
        # Should have at least some violations
        total = sum(len(v) for v in summary.values())
        assert total > 0

    def test_summary_clean_html(self):
        html = "<p>Clean</p>"
        summary = check_ai_slop_summary(html)
        total = sum(len(v) for v in summary.values())
        assert total == 0
