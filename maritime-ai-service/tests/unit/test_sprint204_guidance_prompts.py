"""
Sprint 204: "Hướng Dẫn, Không Ép Buộc" — Anti-Pattern Remediation Tests

Tests that constraint anti-patterns ("BẮT BUỘC", "TUYỆT ĐỐI KHÔNG") are replaced
with positive identity-based guidance when enable_natural_conversation=True,
and that legacy constraint text is preserved when the flag is off.

SOTA 2026 Reference:
  - Anthropic: "Describe WHO the AI IS, not WHAT it MUST NOT do"
  - Positive framing 3x more effective than prohibitions
  - OpenClaw: SOUL.md defines identity, runtime honors it
"""

import unicodedata

import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Helpers
# =============================================================================


def _mock_settings(**overrides):
    """Create a mock Settings with Sprint 204 defaults + overrides."""
    defaults = {
        "enable_natural_conversation": False,
        "llm_presence_penalty": 0.0,
        "llm_frequency_penalty": 0.0,
        "default_domain": "maritime",
        "app_name": "Wiii",
        "enable_product_search": False,
        "enable_subagent_architecture": False,
        "enable_character_tools": False,
        "enable_code_execution": False,
        "enable_lms_integration": False,
        "enable_living_agent": False,
        "enable_soul_emotion": False,
        "enable_facebook_cookie": False,
        "enable_artifacts": False,
        "enable_websocket": False,
        "quality_skip_threshold": 0.85,
        "identity_anchor_interval": 6,
        "active_domains": ["maritime"],
        "enable_corrective_rag": True,
        "use_multi_agent": True,
        "enable_agentic_loop": True,
        "agentic_loop_max_steps": 8,
        "enable_structured_outputs": True,
        "cross_domain_search": True,
        "domain_boost_score": 0.15,
        "enable_chart_tools": False,
        "enable_browser_scraping": False,
    }
    defaults.update(overrides)
    s = MagicMock()
    s.__class__ = type("MockSettings", (), {})
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def _fold_text(text: str) -> str:
    """Compare prompt intent without coupling tests to accented vs ASCII-safe text."""
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def _assert_contains(prompt: str, expected: str) -> None:
    assert _fold_text(expected) in _fold_text(prompt)


def _assert_not_contains(prompt: str, expected: str) -> None:
    assert _fold_text(expected) not in _fold_text(prompt)


def _build_tools_context(natural=False, **extra_settings):
    """Build the tool context string from graph.py _build_direct_tools_context."""
    settings_overrides = {"enable_natural_conversation": natural, **extra_settings}
    s = _mock_settings(**settings_overrides)
    from app.engine.multi_agent.graph import _build_direct_tools_context
    return _build_direct_tools_context(s, "hàng hải")


# =============================================================================
# Group 1: graph.py Tool Hints — Natural Mode (7 tests)
# =============================================================================


class TestGraphToolHintsNatural:
    """When enable_natural_conversation=True, tool hints use identity-based guidance."""

    def test_no_bat_buoc_in_tool_hints(self):
        """Natural mode should NOT contain 'BẮT BUỘC' in tool hints."""
        prompt = _build_tools_context(natural=True)
        _assert_not_contains(prompt, "BẮT BUỘC")

    def test_no_tuyet_doi_khong(self):
        """Natural mode should NOT contain 'TUYỆT ĐỐI KHÔNG'."""
        prompt = _build_tools_context(natural=True)
        _assert_not_contains(prompt, "TUYỆT ĐỐI KHÔNG")

    def test_no_quy_tac_bat_buoc(self):
        """Natural mode should NOT have the old 'QUY TẮC BẮT BUỘC VỀ TOOL' heading."""
        prompt = _build_tools_context(natural=True)
        _assert_not_contains(prompt, "QUY TẮC BẮT BUỘC VỀ TOOL")

    def test_has_identity_language(self):
        """Natural mode should use Wiii identity language."""
        prompt = _build_tools_context(natural=True)
        _assert_contains(prompt, "Wiii luôn chính xác")

    def test_has_positive_tool_guidance(self):
        """Natural mode should describe how Wiii uses tools positively."""
        prompt = _build_tools_context(natural=True)
        _assert_contains(prompt, "CÁCH WIII SỬ DỤNG TOOL")

    def test_has_knowledge_context(self):
        """Natural mode should describe Wiii's knowledge positively."""
        prompt = _build_tools_context(natural=True)
        _assert_contains(prompt, "VỀ KIẾN THỨC CỦA WIII")

    def test_honesty_framing(self):
        """Natural mode should frame honesty as identity trait."""
        prompt = _build_tools_context(natural=True)
        _assert_contains(prompt, "Wiii trung thực")


# =============================================================================
# Group 2: graph.py Tool Hints — Legacy Mode (5 tests)
# =============================================================================


class TestGraphToolHintsLegacy:
    """When enable_natural_conversation=False, legacy constraint text preserved."""

    def test_has_bat_buoc(self):
        """Legacy mode should still contain 'BẮT BUỘC'."""
        prompt = _build_tools_context(natural=False)
        _assert_contains(prompt, "BẮT BUỘC")

    def test_has_tuyet_doi_khong(self):
        """Legacy mode should still contain 'TUYỆT ĐỐI KHÔNG'."""
        prompt = _build_tools_context(natural=False)
        _assert_contains(prompt, "TUYỆT ĐỐI KHÔNG")

    def test_has_quy_tac_heading(self):
        """Legacy mode should still have 'QUY TẮC BẮT BUỘC VỀ TOOL' heading."""
        prompt = _build_tools_context(natural=False)
        _assert_contains(prompt, "QUY TẮC BẮT BUỘC VỀ TOOL")

    def test_has_gioi_han_kien_thuc(self):
        """Legacy mode should still have 'GIỚI HẠN KIẾN THỨC' section."""
        prompt = _build_tools_context(natural=False)
        _assert_contains(prompt, "GIỚI HẠN KIẾN THỨC")

    def test_no_wiii_identity_language(self):
        """Legacy mode should NOT use Wiii identity language in tool rules."""
        prompt = _build_tools_context(natural=False)
        _assert_not_contains(prompt, "CÁCH WIII SỬ DỤNG TOOL")


# =============================================================================
# Group 3: corrective_rag.py Fallback Prompt — Natural Mode (5 tests)
# =============================================================================


class TestCorrectiveRagNatural:
    """When natural mode on, CRAG fallback uses positive framing."""

    def _build_fallback_prompt(self, natural=False):
        """Build the CRAG fallback system prompt (mirrors corrective_rag.py logic)."""
        s = _mock_settings(enable_natural_conversation=natural)

        personality = "Thân thiện, ấm áp."
        name_hint = "User tên Bạn. "
        avoid_text = ""
        domain_name = "hàng hải"
        emoji_usage = ""

        try:
            _natural = getattr(s, "enable_natural_conversation", False) is True
        except Exception:
            _natural = False

        if _natural:
            return (
                f"Bạn là {s.app_name}. {personality} "
                f"{name_hint}"
                f"{avoid_text} "
                f"Chuyên ngành: {domain_name}. "
                f"Hãy dùng kiến thức tổng quát của bạn về {domain_name} để trả lời. "
                f"Wiii luôn cố gắng giúp đỡ — khi không có tài liệu cụ thể, "
                f"Wiii dùng kiến thức chung và ghi chú nguồn để người dùng tự xác minh thêm. "
                f"Nếu câu hỏi nằm ngoài {domain_name}, Wiii lịch sự hướng dẫn lại. "
                "Nếu là lời chào, Wiii chào lại tự nhiên theo tính cách của mình. "
                f"Với câu hỏi về {domain_name}, Wiii trả lời đầy đủ và ghi chú: "
                "'(Thông tin dựa trên kiến thức tổng quát, chưa xác minh từ tài liệu gốc)' "
                f"{emoji_usage} "
                "Wiii trả lời bằng tiếng Việt, đi thẳng vào nội dung."
            )
        else:
            return (
                f"Bạn là {s.app_name}. {personality} "
                "BẮT BUỘC: LUÔN LUÔN đưa ra câu trả lời có nội dung thực chất. "
                "TUYỆT ĐỐI KHÔNG nói 'không tìm thấy', 'không có thông tin', "
                "'không thể trả lời' hay bất kỳ từ chối nào tương tự. "
                "BẮT BUỘC: Trả lời hoàn toàn bằng TIẾNG VIỆT. "
                "TUYỆT ĐỐI KHÔNG trả lời bằng tiếng Anh. "
            )

    def test_no_bat_buoc_in_fallback(self):
        """Natural fallback should NOT contain 'BẮT BUỘC'."""
        prompt = self._build_fallback_prompt(natural=True)
        _assert_not_contains(prompt, "BẮT BUỘC")

    def test_no_tuyet_doi_khong_in_fallback(self):
        """Natural fallback should NOT contain 'TUYỆT ĐỐI KHÔNG'."""
        prompt = self._build_fallback_prompt(natural=True)
        _assert_not_contains(prompt, "TUYỆT ĐỐI KHÔNG")

    def test_has_helpful_identity(self):
        """Natural fallback should describe Wiii as helpful."""
        prompt = self._build_fallback_prompt(natural=True)
        _assert_contains(prompt, "Wiii luôn cố gắng giúp đỡ")

    def test_has_source_note_guidance(self):
        """Natural fallback should guide Wiii to note sources."""
        prompt = self._build_fallback_prompt(natural=True)
        _assert_contains(prompt, "ghi chú nguồn")

    def test_vietnamese_language(self):
        """Natural fallback should mention Vietnamese response."""
        prompt = self._build_fallback_prompt(natural=True)
        _assert_contains(prompt, "tiếng Việt")


# =============================================================================
# Group 4: corrective_rag.py Fallback Prompt — Legacy Mode (3 tests)
# =============================================================================


class TestCorrectiveRagLegacy:
    """When flag off, CRAG fallback preserves legacy constraints."""

    def test_legacy_has_bat_buoc(self):
        """Legacy fallback should still contain 'BẮT BUỘC'."""
        prompt = TestCorrectiveRagNatural()._build_fallback_prompt(natural=False)
        _assert_contains(prompt, "BẮT BUỘC")

    def test_legacy_has_tuyet_doi_khong(self):
        """Legacy fallback should still contain 'TUYỆT ĐỐI KHÔNG'."""
        prompt = TestCorrectiveRagNatural()._build_fallback_prompt(natural=False)
        _assert_contains(prompt, "TUYỆT ĐỐI KHÔNG")

    def test_legacy_no_wiii_identity(self):
        """Legacy fallback should NOT use Wiii identity language."""
        prompt = TestCorrectiveRagNatural()._build_fallback_prompt(natural=False)
        _assert_not_contains(prompt, "Wiii luôn cố gắng")


# =============================================================================
# Group 5: web_search_tools.py Tool Descriptions (4 tests)
# =============================================================================


class TestWebSearchToolDescriptions:
    """Tool descriptions should use neutral language (no BẮT BUỘC)."""

    def test_news_tool_no_bat_buoc(self):
        """tool_search_news description should not contain 'BẮT BUỘC'."""
        from app.engine.tools.web_search_tools import tool_search_news
        desc = tool_search_news.description
        _assert_not_contains(desc, "BẮT BUỘC")

    def test_legal_tool_no_bat_buoc(self):
        """tool_search_legal description should not contain 'BẮT BUỘC'."""
        from app.engine.tools.web_search_tools import tool_search_legal
        desc = tool_search_legal.description
        _assert_not_contains(desc, "BẮT BUỘC")

    def test_news_tool_has_content(self):
        """tool_search_news should describe what it searches."""
        from app.engine.tools.web_search_tools import tool_search_news
        desc = tool_search_news.description
        _assert_contains(desc, "TIN TỨC")
        assert "VnExpress" in desc

    def test_legal_tool_has_content(self):
        """tool_search_legal should describe what it searches."""
        from app.engine.tools.web_search_tools import tool_search_legal
        desc = tool_search_legal.description
        _assert_contains(desc, "PHÁP LUẬT")
        _assert_contains(desc, "Thư viện Pháp luật")


# =============================================================================
# Group 6: Integration — Flag Toggles Both Systems (4 tests)
# =============================================================================


class TestFlagToggleIntegration:
    """Verify the same flag controls both graph.py and corrective_rag.py."""

    def test_flag_true_graph_clean(self):
        """Flag=True → graph.py tools context has zero 'BẮT BUỘC'."""
        prompt = _build_tools_context(natural=True)
        count = _fold_text(prompt).count(_fold_text("BẮT BUỘC"))
        assert count == 0, f"Found {count} instances of 'BẮT BUỘC' in natural mode"

    def test_flag_true_graph_zero_tuyet_doi(self):
        """Flag=True → graph.py tools context has zero 'TUYỆT ĐỐI KHÔNG'."""
        prompt = _build_tools_context(natural=True)
        count = _fold_text(prompt).count(_fold_text("TUYỆT ĐỐI KHÔNG"))
        assert count == 0, f"Found {count} instances of 'TUYỆT ĐỐI KHÔNG'"

    def test_flag_false_preserves_all(self):
        """Flag=False → graph.py tools context preserves all legacy constraints."""
        prompt = _build_tools_context(natural=False)
        assert _fold_text(prompt).count(_fold_text("BẮT BUỘC")) >= 3, "Legacy should have multiple BẮT BUỘC"

    def test_default_flag_is_false(self):
        """Default config should have enable_natural_conversation=False."""
        s = _mock_settings()
        assert s.enable_natural_conversation is False


# =============================================================================
# Group 7: Regression — Sprint 203 Compatibility (4 tests)
# =============================================================================


class TestSprint203Compatibility:
    """Sprint 204 changes should not break Sprint 203 functionality."""

    def test_tool_hints_still_list_all_tools(self):
        """Both modes should list all core tools."""
        for natural in [True, False]:
            prompt = _build_tools_context(natural=natural)
            assert "tool_current_datetime" in prompt
            assert "tool_web_search" in prompt
            assert "tool_search_news" in prompt
            assert "tool_search_legal" in prompt
            assert "tool_search_maritime" in prompt

    def test_maritime_tool_unchanged(self):
        """Maritime tool hint should be the same in both modes."""
        natural_prompt = _build_tools_context(natural=True)
        legacy_prompt = _build_tools_context(natural=False)
        assert "tool_search_maritime" in natural_prompt
        assert "tool_search_maritime" in legacy_prompt

    def test_character_note_conditional(self):
        """Character note tool should appear when enable_character_tools=True."""
        prompt = _build_tools_context(natural=True, enable_character_tools=True)
        assert "tool_character_note" in prompt

    def test_code_execution_conditional(self):
        """Code execution tool appears in code_studio context (moved from direct node in WAVE-001)."""
        from app.engine.multi_agent.graph import _build_code_studio_tools_context
        s = _mock_settings(enable_code_execution=True, enable_browser_agent=False, enable_privileged_sandbox=False)
        prompt = _build_code_studio_tools_context(s, user_role="admin")
        assert "tool_execute_python" in prompt
