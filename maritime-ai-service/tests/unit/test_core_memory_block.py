"""
Tests for app.engine.semantic_memory.core_memory_block

Sprint 73: Core Memory Block — compiled user profile injected into system prompt.
Tests cover:
  - _compile() with full, partial, empty, and sectional facts
  - _truncate() short-pass and long-block trimming
  - get_block() feature flag, empty user, cache, fetch, error handling
  - invalidate / invalidate_all cache management
  - get_core_memory_block() singleton
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.semantic_memory.core_memory_block import (
    CoreMemoryBlock,
    get_core_memory_block,
    _IDENTITY_FIELDS,
    _SECTION_GROUPS,
    _SECTION_LABELS,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def block():
    """Fresh CoreMemoryBlock instance (no singleton)."""
    return CoreMemoryBlock()


@pytest.fixture
def full_facts():
    """Complete facts dict covering every known field."""
    return {
        "name": "Minh",
        "age": "25",
        "location": "Sai Gon",
        "role": "Sinh vien",
        "level": "Nam 4",
        "organization": "DH Hang Hai",
        "goal": "Thi COLREGs",
        "weakness": "Quy tac 15",
        "strength": "Quy tac 7",
        "learning_style": "Truc quan",
        "preference": "Video",
        "hobby": "Doc sach",
        "interest": "Hang hai",
        "emotion": "Vui",
        "recent_topic": "COLREGs Rule 15",
    }


@pytest.fixture
def mock_semantic_memory():
    """AsyncMock semantic memory engine."""
    return AsyncMock()


# ===========================================================================
# _compile tests
# ===========================================================================

class TestCompile:
    """Tests for CoreMemoryBlock._compile()."""

    def test_compile_full_facts_correct_structure(self, block, full_facts):
        """1. Full facts produce correct markdown structure with all sections."""
        result = block._compile(full_facts)

        # Header
        assert result.startswith("## Ho so nguoi dung") or result.startswith("## Hồ sơ người dùng")
        assert "## Hồ sơ người dùng" in result

        # Identity line
        assert "**Tên:** Minh" in result
        assert "**Tuổi:** 25" in result
        assert "**Nơi ở:** Sai Gon" in result

        # Professional line
        assert "**Vai trò:** Sinh vien" in result
        assert "**Cấp bậc:** Nam 4" in result
        assert "**Tổ chức:** DH Hang Hai" in result

        # Sections
        assert "### Học tập" in result
        assert "- Mục tiêu: Thi COLREGs" in result
        assert "- Điểm yếu: Quy tac 15" in result
        assert "- Điểm mạnh: Quy tac 7" in result

        assert "### Cá nhân" in result
        assert "- Sở thích: Doc sach" in result

        assert "### Ngữ cảnh" in result
        assert "- Tâm trạng: Vui" in result
        assert "- Chủ đề gần đây: COLREGs Rule 15" in result

    def test_compile_partial_facts_name_role_only(self, block):
        """2. Partial facts (only name + role) render identity + professional lines."""
        facts = {"name": "Lan", "role": "Giang vien"}
        result = block._compile(facts)

        assert "## Hồ sơ người dùng" in result
        assert "**Tên:** Lan" in result
        assert "**Vai trò:** Giang vien" in result
        # No sections
        assert "### Học tập" not in result
        assert "### Cá nhân" not in result
        assert "### Ngữ cảnh" not in result

    def test_compile_empty_dict_returns_empty(self, block):
        """3. Empty dict produces empty string (only header, len<=1)."""
        result = block._compile({})
        assert result == ""

    def test_compile_only_identity_fields(self, block):
        """4. Only identity fields → identity line, no professional, no sections."""
        facts = {"name": "An", "age": "30", "location": "Ha Noi"}
        result = block._compile(facts)

        assert "## Hồ sơ người dùng" in result
        assert "**Tên:** An" in result
        assert "**Tuổi:** 30" in result
        assert "**Nơi ở:** Ha Noi" in result
        # No professional or group sections
        assert "**Vai trò:**" not in result
        assert "### Học tập" not in result
        assert "### Cá nhân" not in result
        assert "### Ngữ cảnh" not in result

    def test_compile_learning_fields_section(self, block):
        """5. Learning fields produce '### Hoc tap' section."""
        facts = {"name": "Test", "goal": "Pass exam", "weakness": "Rule 8"}
        result = block._compile(facts)

        assert "### Học tập" in result
        assert "- Mục tiêu: Pass exam" in result
        assert "- Điểm yếu: Rule 8" in result

    def test_compile_personal_fields_section(self, block):
        """6. Personal fields produce '### Ca nhan' section."""
        facts = {"name": "User", "hobby": "Swimming", "interest": "Ships"}
        result = block._compile(facts)

        assert "### Cá nhân" in result
        assert "- Sở thích: Swimming" in result
        assert "- Quan tâm: Ships" in result

    def test_compile_volatile_fields_section(self, block):
        """7. Volatile fields produce '### Ngu canh' section."""
        facts = {"name": "User", "emotion": "Happy", "recent_topic": "Navigation"}
        result = block._compile(facts)

        assert "### Ngữ cảnh" in result
        assert "- Tâm trạng: Happy" in result
        assert "- Chủ đề gần đây: Navigation" in result

    def test_compile_identity_inline_separated_by_pipe(self, block):
        """Identity fields are joined by ' | ' separator on one line."""
        facts = {"name": "A", "age": "20", "location": "B"}
        result = block._compile(facts)
        lines = result.split("\n")
        identity_line = lines[1]  # Line after header
        assert " | " in identity_line
        assert identity_line.count(" | ") == 2  # 3 parts, 2 separators

    def test_compile_professional_line_rendering(self, block):
        """20. Professional line renders role + level + org with pipe separator."""
        facts = {"role": "Captain", "level": "Senior", "organization": "Navy"}
        result = block._compile(facts)

        lines = result.split("\n")
        # The professional line should be right after header (no identity line)
        prof_line = lines[1]
        assert "**Vai trò:** Captain" in prof_line
        assert "**Cấp bậc:** Senior" in prof_line
        assert "**Tổ chức:** Navy" in prof_line
        assert " | " in prof_line

    def test_compile_unknown_fields_ignored(self, block):
        """Unknown fields not in _SECTION_LABELS are silently ignored."""
        facts = {"name": "Test", "unknown_field": "value", "another": "data"}
        result = block._compile(facts)
        assert "unknown_field" not in result
        assert "another" not in result
        assert "**Tên:** Test" in result

    def test_compile_falsy_values_skipped(self, block):
        """Fields with empty string or None values are skipped."""
        facts = {"name": "", "age": None, "role": "Student"}
        result = block._compile(facts)
        assert "**Tên:**" not in result
        assert "**Tuổi:**" not in result
        assert "**Vai trò:** Student" in result

    def test_compile_section_order_preserved(self, block, full_facts):
        """Sections appear in order: Hoc tap, Ca nhan, Ngu canh."""
        result = block._compile(full_facts)
        idx_learn = result.index("### Học tập")
        idx_personal = result.index("### Cá nhân")
        idx_context = result.index("### Ngữ cảnh")
        assert idx_learn < idx_personal < idx_context


# ===========================================================================
# _truncate tests
# ===========================================================================

class TestTruncate:
    """Tests for CoreMemoryBlock._truncate()."""

    def test_truncate_short_block_unchanged(self, block):
        """8. Block within limit is returned as-is."""
        short = "## Header\nLine 1\nLine 2"
        result = block._truncate(short, max_tokens=800)
        assert result == short

    def test_truncate_long_block_removes_bottom_lines(self, block):
        """9. Block exceeding limit has bottom lines removed."""
        # max_tokens=5 → max_chars=20
        lines = ["## Header", "AAAA", "BBBB", "CCCC", "DDDD", "EEEE", "FFFF"]
        long_block = "\n".join(lines)
        result = block._truncate(long_block, max_tokens=5)

        assert len(result) <= 20
        # Header should be preserved
        assert result.startswith("## Header")
        # Last lines should be removed
        assert "FFFF" not in result

    def test_truncate_exact_boundary(self, block):
        """Block exactly at limit is unchanged."""
        text = "A" * 100  # 100 chars
        result = block._truncate(text, max_tokens=25)  # 25*4=100
        assert result == text

    def test_truncate_preserves_minimum_two_lines(self, block):
        """Truncation stops when only 2 lines remain (while len(lines) > 2)."""
        lines = ["## Header", "Important line"] + [f"Line {i}" for i in range(50)]
        long_block = "\n".join(lines)
        result = block._truncate(long_block, max_tokens=1)  # Very tight: 4 chars
        result_lines = result.split("\n")
        assert len(result_lines) >= 2

    def test_truncate_empty_block(self, block):
        """Empty block returns empty string."""
        result = block._truncate("", max_tokens=800)
        assert result == ""


# ===========================================================================
# get_block tests (async)
# ===========================================================================

class TestGetBlock:
    """Tests for CoreMemoryBlock.get_block()."""

    @pytest.mark.asyncio
    async def test_get_block_disabled_returns_empty(self, block):
        """10. Returns '' when enable_core_memory_block=False."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = False
            result = await block.get_block("user1", facts_dict={"name": "Test"})
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_block_empty_user_id_returns_empty(self, block):
        """11. Returns '' for empty user_id."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            result = await block.get_block("")
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_block_none_user_id_returns_empty(self, block):
        """Returns '' for None user_id."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            result = await block.get_block(None)
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_block_with_prefetched_facts(self, block):
        """12. Uses pre-fetched facts_dict, no semantic_memory call."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            result = await block.get_block(
                "user1",
                facts_dict={"name": "Minh", "role": "Student"},
            )
            assert "**Tên:** Minh" in result
            assert "**Vai trò:** Student" in result

    @pytest.mark.asyncio
    async def test_get_block_fetches_from_semantic_memory(self, block, mock_semantic_memory):
        """13. Fetches from semantic_memory.get_user_facts() when facts_dict is None."""
        mock_semantic_memory.get_user_facts = AsyncMock(return_value={"name": "Lan", "hobby": "Sailing"})

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            result = await block.get_block("user2", semantic_memory=mock_semantic_memory)

            mock_semantic_memory.get_user_facts.assert_awaited_once_with("user2")
            assert "**Tên:** Lan" in result
            assert "- Sở thích: Sailing" in result

    @pytest.mark.asyncio
    async def test_get_block_empty_facts_from_semantic_memory(self, block, mock_semantic_memory):
        """14. Returns '' when semantic_memory returns empty dict."""
        mock_semantic_memory.get_user_facts = AsyncMock(return_value={})

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            result = await block.get_block("user3", semantic_memory=mock_semantic_memory)
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_block_caches_result(self, block, mock_semantic_memory):
        """15. Second call within TTL returns cached value without re-fetch."""
        mock_semantic_memory.get_user_facts = AsyncMock(return_value={"name": "Cached"})

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            # First call — fetches
            result1 = await block.get_block("user4", semantic_memory=mock_semantic_memory)
            assert "**Tên:** Cached" in result1

            # Second call — from cache (no second fetch)
            result2 = await block.get_block("user4", semantic_memory=mock_semantic_memory)
            assert result2 == result1
            mock_semantic_memory.get_user_facts.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_block_cache_expired_refetches(self, block, mock_semantic_memory):
        """Expired cache entry triggers re-fetch."""
        mock_semantic_memory.get_user_facts = AsyncMock(return_value={"name": "Fresh"})

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 1  # 1 second TTL
            mock_settings.core_memory_max_tokens = 800

            result1 = await block.get_block("user5", semantic_memory=mock_semantic_memory)
            assert "**Tên:** Fresh" in result1

        # Manually expire cache entry by backdating timestamp
        block._cache["user5"] = (block._cache["user5"][0], time.time() - 10)

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 1
            mock_settings.core_memory_max_tokens = 800

            mock_semantic_memory.get_user_facts = AsyncMock(return_value={"name": "Refreshed"})
            result2 = await block.get_block("user5", semantic_memory=mock_semantic_memory)
            assert "**Tên:** Refreshed" in result2

    @pytest.mark.asyncio
    async def test_get_block_semantic_memory_exception_returns_empty(self, block, mock_semantic_memory):
        """18. Handles semantic_memory exception gracefully — returns ''."""
        mock_semantic_memory.get_user_facts = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            result = await block.get_block("user6", semantic_memory=mock_semantic_memory)
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_block_no_semantic_memory_and_no_facts_returns_empty(self, block):
        """Returns '' when facts_dict is None and semantic_memory is None."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            result = await block.get_block("user7")
            assert result == ""

    @pytest.mark.asyncio
    async def test_get_block_empty_facts_cached_as_empty(self, block, mock_semantic_memory):
        """Empty facts result is cached — second call doesn't re-fetch."""
        mock_semantic_memory.get_user_facts = AsyncMock(return_value={})

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            await block.get_block("user_empty", semantic_memory=mock_semantic_memory)
            result2 = await block.get_block("user_empty", semantic_memory=mock_semantic_memory)
            assert result2 == ""
            # Only one fetch because empty result was cached
            mock_semantic_memory.get_user_facts.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_block_applies_truncation(self, block):
        """get_block applies _truncate to the compiled block."""
        # Build facts that produce a long block, with very small max_tokens
        facts = {
            "name": "A" * 100,
            "age": "B" * 100,
            "location": "C" * 100,
            "role": "D" * 100,
            "goal": "E" * 100,
            "weakness": "F" * 100,
            "hobby": "G" * 100,
            "emotion": "H" * 100,
        }

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 10  # Very tight: 40 chars

            result = await block.get_block("user_trunc", facts_dict=facts)
            # The result should be truncated — much shorter than full compilation
            full = block._compile(facts)
            assert len(result) < len(full)


# ===========================================================================
# Cache management tests
# ===========================================================================

class TestCacheManagement:
    """Tests for invalidate / invalidate_all."""

    @pytest.mark.asyncio
    async def test_invalidate_removes_user(self, block):
        """16. invalidate() removes a specific user from cache."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            await block.get_block("user_a", facts_dict={"name": "A"})
            await block.get_block("user_b", facts_dict={"name": "B"})

            assert "user_a" in block._cache
            assert "user_b" in block._cache

            block.invalidate("user_a")

            assert "user_a" not in block._cache
            assert "user_b" in block._cache

    @pytest.mark.asyncio
    async def test_invalidate_all_clears_cache(self, block):
        """17. invalidate_all() clears entire cache."""
        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            await block.get_block("x", facts_dict={"name": "X"})
            await block.get_block("y", facts_dict={"name": "Y"})

            assert len(block._cache) == 2

            block.invalidate_all()

            assert len(block._cache) == 0

    def test_invalidate_nonexistent_user_no_error(self, block):
        """invalidate() on non-existent user does not raise."""
        block.invalidate("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_invalidate_forces_refetch(self, block, mock_semantic_memory):
        """After invalidate, next get_block fetches fresh data."""
        mock_semantic_memory.get_user_facts = AsyncMock(return_value={"name": "Old"})

        with patch("app.engine.semantic_memory.core_memory_block.settings") as mock_settings:
            mock_settings.enable_core_memory_block = True
            mock_settings.core_memory_cache_ttl = 300
            mock_settings.core_memory_max_tokens = 800

            result1 = await block.get_block("user_inv", semantic_memory=mock_semantic_memory)
            assert "**Tên:** Old" in result1

            block.invalidate("user_inv")

            mock_semantic_memory.get_user_facts = AsyncMock(return_value={"name": "New"})
            result2 = await block.get_block("user_inv", semantic_memory=mock_semantic_memory)
            assert "**Tên:** New" in result2


# ===========================================================================
# Singleton tests
# ===========================================================================

class TestSingleton:
    """Tests for get_core_memory_block() singleton."""

    def test_singleton_returns_same_instance(self):
        """19. get_core_memory_block() returns same instance on repeated calls."""
        # Reset singleton for clean test
        import app.engine.semantic_memory.core_memory_block as mod
        original = mod._core_memory_block
        try:
            mod._core_memory_block = None
            instance1 = get_core_memory_block()
            instance2 = get_core_memory_block()
            assert instance1 is instance2
            assert isinstance(instance1, CoreMemoryBlock)
        finally:
            mod._core_memory_block = original

    def test_singleton_creates_core_memory_block_type(self):
        """Singleton creates CoreMemoryBlock instance."""
        import app.engine.semantic_memory.core_memory_block as mod
        original = mod._core_memory_block
        try:
            mod._core_memory_block = None
            instance = get_core_memory_block()
            assert type(instance).__name__ == "CoreMemoryBlock"
        finally:
            mod._core_memory_block = original


# ===========================================================================
# Module-level constants sanity checks
# ===========================================================================

class TestConstants:
    """Sanity checks on module-level constants."""

    def test_identity_fields_tuple(self):
        """_IDENTITY_FIELDS is a tuple of known fields."""
        assert isinstance(_IDENTITY_FIELDS, tuple)
        assert "name" in _IDENTITY_FIELDS
        assert "age" in _IDENTITY_FIELDS
        assert "location" in _IDENTITY_FIELDS

    def test_section_groups_order(self):
        """_SECTION_GROUPS has 3 groups in expected order."""
        assert len(_SECTION_GROUPS) == 3
        group_names = [g[0] for g in _SECTION_GROUPS]
        assert group_names == ["Học tập", "Cá nhân", "Ngữ cảnh"]

    def test_section_labels_cover_all_known_fields(self):
        """Every field referenced in groups and identity is in _SECTION_LABELS."""
        all_fields = set(_IDENTITY_FIELDS)
        all_fields.update({"role", "level", "organization"})
        for _, fields in _SECTION_GROUPS:
            all_fields.update(fields)
        for field in all_fields:
            assert field in _SECTION_LABELS, f"Missing label for field: {field}"
