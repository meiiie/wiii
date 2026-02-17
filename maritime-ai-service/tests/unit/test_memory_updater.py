"""
Tests for app.engine.semantic_memory.memory_updater

Sprint 73: MemoryUpdater — Mem0-style ADD/UPDATE/DELETE/NOOP pipeline.

Tests cover:
  - classify() for all action types (ADD, UPDATE, DELETE, NOOP)
  - classify_batch() with mixed and empty inputs
  - build_revision_metadata() for ADD and UPDATE (with/without existing metadata)
  - summarize_changes() for all action combinations
  - _values_match() edge cases (whitespace, case)
  - _is_negation() Vietnamese patterns
  - MemoryDecision repr
  - confidence passthrough
"""

import json

import pytest

from app.engine.semantic_memory.memory_updater import (
    MemoryAction,
    MemoryDecision,
    MemoryUpdater,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def updater():
    """Default MemoryUpdater instance."""
    return MemoryUpdater()


@pytest.fixture
def updater_custom_threshold():
    """MemoryUpdater with custom similarity threshold."""
    return MemoryUpdater(similarity_threshold=0.85)


# ---------------------------------------------------------------------------
# 1. classify — ADD: new fact_type not in existing
# ---------------------------------------------------------------------------

class TestClassifyAdd:

    def test_add_new_fact_type(self, updater):
        """New fact_type not present in existing_facts results in ADD."""
        result = updater.classify("name", "Minh", existing_facts={})
        assert result.action == MemoryAction.ADD
        assert result.fact_type == "name"
        assert result.new_value == "Minh"
        assert result.old_value is None
        assert result.reason == "New fact type"

    def test_add_when_other_types_exist(self, updater):
        """ADD when existing has other fact types but not the target type."""
        existing = {"role": "student", "location": "HCM"}
        result = updater.classify("name", "Lan", existing_facts=existing)
        assert result.action == MemoryAction.ADD
        assert result.fact_type == "name"
        assert result.new_value == "Lan"

    def test_add_strips_whitespace(self, updater):
        """New value is stripped before classification."""
        result = updater.classify("name", "  Minh  ", existing_facts={})
        assert result.action == MemoryAction.ADD
        assert result.new_value == "Minh"


# ---------------------------------------------------------------------------
# 2-3. classify — NOOP: identical value (exact and case-insensitive)
# ---------------------------------------------------------------------------

class TestClassifyNoop:

    def test_noop_identical_value(self, updater):
        """Same type, identical value results in NOOP."""
        existing = {"name": "Minh"}
        result = updater.classify("name", "Minh", existing_facts=existing)
        assert result.action == MemoryAction.NOOP
        assert result.reason == "Identical value"
        assert result.old_value == "Minh"

    def test_noop_case_insensitive(self, updater):
        """NOOP when values differ only in case ('Minh' vs 'minh')."""
        existing = {"name": "Minh"}
        result = updater.classify("name", "minh", existing_facts=existing)
        assert result.action == MemoryAction.NOOP
        assert result.reason == "Identical value"

    def test_noop_case_insensitive_reverse(self, updater):
        """NOOP when existing is lowercase and new is uppercase."""
        existing = {"name": "minh"}
        result = updater.classify("name", "MINH", existing_facts=existing)
        assert result.action == MemoryAction.NOOP

    def test_noop_with_whitespace_in_existing(self, updater):
        """NOOP when existing value has whitespace that matches after strip."""
        existing = {"name": "  minh  "}
        result = updater.classify("name", "minh", existing_facts=existing)
        assert result.action == MemoryAction.NOOP


# ---------------------------------------------------------------------------
# 4. classify — UPDATE: same type, different value
# ---------------------------------------------------------------------------

class TestClassifyUpdate:

    def test_update_different_value(self, updater):
        """Same type but different value results in UPDATE."""
        existing = {"role": "Sinh vien"}
        result = updater.classify("role", "Giang vien", existing_facts=existing)
        assert result.action == MemoryAction.UPDATE
        assert result.fact_type == "role"
        assert result.new_value == "Giang vien"
        assert result.old_value == "Sinh vien"
        assert result.reason == "Value changed"

    def test_update_location_change(self, updater):
        """UPDATE when location changes."""
        existing = {"location": "Sai Gon"}
        result = updater.classify("location", "Ha Noi", existing_facts=existing)
        assert result.action == MemoryAction.UPDATE
        assert result.old_value == "Sai Gon"
        assert result.new_value == "Ha Noi"


# ---------------------------------------------------------------------------
# 5. classify — DELETE: negation + existing fact
# ---------------------------------------------------------------------------

class TestClassifyDelete:

    def test_delete_negation_existing(self, updater):
        """Negation pattern with existing fact results in DELETE."""
        existing = {"location": "Sai Gon"}
        result = updater.classify(
            "location", "không còn ở Sai Gon", existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE
        assert result.old_value == "Sai Gon"
        assert result.reason == "Negation detected"

    def test_delete_khong_phai_pattern(self, updater):
        """DELETE with 'không phải' negation pattern."""
        existing = {"role": "Sinh vien"}
        result = updater.classify(
            "role", "không phải SV nữa", existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE
        assert result.old_value == "Sinh vien"

    def test_delete_da_bo_pattern(self, updater):
        """DELETE with 'đã bỏ' negation pattern."""
        existing = {"hobby": "bong da"}
        result = updater.classify(
            "hobby", "đã bỏ chơi bóng đá", existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE

    def test_delete_het_roi_pattern(self, updater):
        """DELETE with 'hết rồi' negation pattern."""
        existing = {"subscription": "premium"}
        result = updater.classify(
            "subscription", "hết rồi", existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE

    def test_delete_thoi_roi_pattern(self, updater):
        """DELETE with 'thôi rồi' negation pattern."""
        existing = {"job": "dev"}
        result = updater.classify(
            "job", "thôi rồi", existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE


# ---------------------------------------------------------------------------
# 6. classify — NOOP: negation for non-existing fact
# ---------------------------------------------------------------------------

class TestClassifyNegationNoop:

    def test_noop_negation_non_existing(self, updater):
        """Negation for non-existing fact type results in NOOP."""
        result = updater.classify(
            "location", "không còn ở SG", existing_facts={}
        )
        assert result.action == MemoryAction.NOOP
        assert result.reason == "Negation for non-existing fact"

    def test_noop_negation_different_type_exists(self, updater):
        """Negation for a type not in existing (but other types exist) is NOOP."""
        existing = {"name": "Minh"}
        result = updater.classify(
            "location", "không phải SV nữa", existing_facts=existing
        )
        assert result.action == MemoryAction.NOOP
        assert result.reason == "Negation for non-existing fact"


# ---------------------------------------------------------------------------
# 7. classify — various negation patterns
# ---------------------------------------------------------------------------

class TestNegationPatterns:

    @pytest.mark.parametrize("negation_value", [
        "không còn ở SG",
        "không phải sinh viên",
        "hết rồi",
        "bỏ rồi",
        "không nữa",
        "thôi rồi",
        "đã bỏ việc",
        "không làm nữa",
    ])
    def test_all_negation_patterns_trigger_delete(self, updater, negation_value):
        """All Vietnamese negation patterns result in DELETE when fact exists."""
        existing = {"target": "old_value"}
        result = updater.classify(
            "target", negation_value, existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE, (
            f"Pattern '{negation_value}' should trigger DELETE"
        )

    def test_negation_case_insensitive(self, updater):
        """Negation check is case-insensitive."""
        existing = {"role": "SV"}
        result = updater.classify(
            "role", "KHÔNG CÒN là SV", existing_facts=existing
        )
        assert result.action == MemoryAction.DELETE

    def test_non_negation_not_deleted(self, updater):
        """Regular value without negation patterns is not classified as DELETE."""
        existing = {"name": "Minh"}
        result = updater.classify(
            "name", "Lan", existing_facts=existing
        )
        assert result.action == MemoryAction.UPDATE


# ---------------------------------------------------------------------------
# 8-9. classify_batch
# ---------------------------------------------------------------------------

class TestClassifyBatch:

    def test_batch_mixed_actions(self, updater):
        """Batch with ADD, UPDATE, NOOP facts."""
        existing = {"name": "Minh", "role": "SV"}
        extracted = [
            {"fact_type": "name", "value": "Minh", "confidence": 0.95},   # NOOP
            {"fact_type": "role", "value": "GV", "confidence": 0.88},     # UPDATE
            {"fact_type": "location", "value": "HCM", "confidence": 0.9}, # ADD
        ]
        decisions = updater.classify_batch(extracted, existing)
        assert len(decisions) == 3
        assert decisions[0].action == MemoryAction.NOOP
        assert decisions[1].action == MemoryAction.UPDATE
        assert decisions[2].action == MemoryAction.ADD

    def test_batch_empty_list(self, updater):
        """Empty extracted_facts returns empty decisions list."""
        decisions = updater.classify_batch([], {"name": "Minh"})
        assert decisions == []

    def test_batch_all_adds(self, updater):
        """Batch where all facts are new (ADD)."""
        extracted = [
            {"fact_type": "name", "value": "Minh"},
            {"fact_type": "role", "value": "SV"},
        ]
        decisions = updater.classify_batch(extracted, {})
        assert all(d.action == MemoryAction.ADD for d in decisions)

    def test_batch_with_negation(self, updater):
        """Batch containing a negation value triggers DELETE."""
        existing = {"location": "SG"}
        extracted = [
            {"fact_type": "location", "value": "không còn ở SG", "confidence": 0.8},
        ]
        decisions = updater.classify_batch(extracted, existing)
        assert decisions[0].action == MemoryAction.DELETE

    def test_batch_default_confidence(self, updater):
        """Batch fact without explicit confidence uses default 0.9."""
        extracted = [{"fact_type": "name", "value": "Minh"}]
        decisions = updater.classify_batch(extracted, {})
        assert decisions[0].confidence == 0.9

    def test_batch_missing_fields_use_defaults(self, updater):
        """Batch fact with missing keys uses empty string defaults."""
        extracted = [{}]
        decisions = updater.classify_batch(extracted, {})
        assert len(decisions) == 1
        assert decisions[0].fact_type == ""
        assert decisions[0].new_value == ""


# ---------------------------------------------------------------------------
# 10-13. build_revision_metadata
# ---------------------------------------------------------------------------

class TestBuildRevisionMetadata:

    def test_add_metadata(self, updater):
        """ADD sets first_seen, access_count=0, empty revision_history."""
        decision = MemoryDecision(
            action=MemoryAction.ADD,
            fact_type="name",
            new_value="Minh",
            confidence=0.95,
        )
        meta = updater.build_revision_metadata(decision)
        assert meta["fact_type"] == "name"
        assert meta["confidence"] == 0.95
        assert meta["access_count"] == 0
        assert meta["revision_history"] == []
        assert "first_seen" in meta

    def test_update_metadata_appends_history(self, updater):
        """UPDATE appends to revision_history with old/new/at."""
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="role",
            new_value="GV",
            old_value="SV",
            confidence=0.9,
        )
        meta = updater.build_revision_metadata(decision)
        assert len(meta["revision_history"]) == 1
        entry = meta["revision_history"][0]
        assert entry["old"] == "SV"
        assert entry["new"] == "GV"
        assert "at" in entry
        assert "first_seen" in meta

    def test_update_with_existing_metadata(self, updater):
        """UPDATE with pre-existing metadata preserves and extends revision_history."""
        existing_meta = {
            "first_seen": "2026-01-01T00:00:00+00:00",
            "access_count": 5,
            "revision_history": [
                {"old": "A", "new": "B", "at": "2026-01-15T00:00:00+00:00"}
            ],
        }
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="role",
            new_value="C",
            old_value="B",
            confidence=0.88,
        )
        meta = updater.build_revision_metadata(decision, existing_metadata=existing_meta)
        assert len(meta["revision_history"]) == 2
        assert meta["revision_history"][0]["old"] == "A"
        assert meta["revision_history"][1]["old"] == "B"
        assert meta["revision_history"][1]["new"] == "C"

    def test_update_preserves_first_seen(self, updater):
        """UPDATE does not overwrite existing first_seen."""
        original_first_seen = "2026-01-01T00:00:00+00:00"
        existing_meta = {
            "first_seen": original_first_seen,
            "revision_history": [],
        }
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="name",
            new_value="Lan",
            old_value="Minh",
        )
        meta = updater.build_revision_metadata(decision, existing_metadata=existing_meta)
        assert meta["first_seen"] == original_first_seen

    def test_update_sets_first_seen_if_missing(self, updater):
        """UPDATE without existing first_seen initializes it."""
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="name",
            new_value="Lan",
            old_value="Minh",
        )
        meta = updater.build_revision_metadata(decision)
        assert "first_seen" in meta

    def test_revision_history_as_json_string(self, updater):
        """Edge case: revision_history stored as JSON string is parsed correctly."""
        existing_meta = {
            "first_seen": "2026-01-01T00:00:00+00:00",
            "revision_history": json.dumps([
                {"old": "X", "new": "Y", "at": "2026-02-01T00:00:00+00:00"}
            ]),
        }
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="status",
            new_value="active",
            old_value="inactive",
        )
        meta = updater.build_revision_metadata(decision, existing_metadata=existing_meta)
        assert isinstance(meta["revision_history"], list)
        assert len(meta["revision_history"]) == 2

    def test_revision_history_as_invalid_string(self, updater):
        """Edge case: revision_history is an unparseable string — reset to empty."""
        existing_meta = {
            "revision_history": "not valid json at all",
        }
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="name",
            new_value="B",
            old_value="A",
        )
        meta = updater.build_revision_metadata(decision, existing_metadata=existing_meta)
        assert isinstance(meta["revision_history"], list)
        assert len(meta["revision_history"]) == 1
        assert meta["revision_history"][0]["old"] == "A"

    def test_add_metadata_no_existing(self, updater):
        """ADD with no existing_metadata (None) initializes cleanly."""
        decision = MemoryDecision(
            action=MemoryAction.ADD,
            fact_type="hobby",
            new_value="coding",
        )
        meta = updater.build_revision_metadata(decision, existing_metadata=None)
        assert meta["fact_type"] == "hobby"
        assert meta["access_count"] == 0


# ---------------------------------------------------------------------------
# 14-19. summarize_changes
# ---------------------------------------------------------------------------

class TestSummarizeChanges:

    def test_adds_only(self, updater):
        """Summary with only ADD decisions."""
        decisions = [
            MemoryDecision(MemoryAction.ADD, "name", "Minh"),
            MemoryDecision(MemoryAction.ADD, "role", "SV"),
        ]
        summary = updater.summarize_changes(decisions)
        assert "Đã ghi nhớ" in summary
        assert "name: Minh" in summary
        assert "role: SV" in summary
        assert "Đã cập nhật" not in summary
        assert "Đã xóa" not in summary

    def test_updates_only(self, updater):
        """Summary with only UPDATE decisions."""
        decisions = [
            MemoryDecision(MemoryAction.UPDATE, "role", "GV", old_value="SV"),
        ]
        summary = updater.summarize_changes(decisions)
        assert "Đã cập nhật" in summary
        assert "role: SV → GV" in summary
        assert "Đã ghi nhớ" not in summary

    def test_deletes_only(self, updater):
        """Summary with only DELETE decisions."""
        decisions = [
            MemoryDecision(MemoryAction.DELETE, "location", "không còn", old_value="SG"),
        ]
        summary = updater.summarize_changes(decisions)
        assert "Đã xóa" in summary
        assert "location" in summary
        assert "Đã ghi nhớ" not in summary
        assert "Đã cập nhật" not in summary

    def test_mixed_actions(self, updater):
        """Summary with ADD, UPDATE, DELETE."""
        decisions = [
            MemoryDecision(MemoryAction.ADD, "name", "Minh"),
            MemoryDecision(MemoryAction.UPDATE, "role", "GV", old_value="SV"),
            MemoryDecision(MemoryAction.DELETE, "location", "không còn", old_value="SG"),
            MemoryDecision(MemoryAction.NOOP, "hobby", "coding", old_value="coding"),
        ]
        summary = updater.summarize_changes(decisions)
        assert "Đã ghi nhớ: name: Minh" in summary
        assert "Đã cập nhật: role: SV → GV" in summary
        assert "Đã xóa: location" in summary

    def test_empty_decisions(self, updater):
        """Empty decisions list returns empty string."""
        summary = updater.summarize_changes([])
        assert summary == ""

    def test_noops_only(self, updater):
        """All NOOP decisions returns empty string."""
        decisions = [
            MemoryDecision(MemoryAction.NOOP, "name", "Minh", old_value="Minh"),
            MemoryDecision(MemoryAction.NOOP, "role", "SV", old_value="SV"),
        ]
        summary = updater.summarize_changes(decisions)
        assert summary == ""

    def test_summary_truncates_adds_at_five(self, updater):
        """ADD summary truncates at 5 items."""
        decisions = [
            MemoryDecision(MemoryAction.ADD, f"fact_{i}", f"val_{i}")
            for i in range(7)
        ]
        summary = updater.summarize_changes(decisions)
        # Should contain first 5 but not 6th and 7th
        assert "fact_0: val_0" in summary
        assert "fact_4: val_4" in summary
        assert "fact_5" not in summary

    def test_summary_truncates_updates_at_three(self, updater):
        """UPDATE summary truncates at 3 items."""
        decisions = [
            MemoryDecision(MemoryAction.UPDATE, f"f_{i}", f"new_{i}", old_value=f"old_{i}")
            for i in range(5)
        ]
        summary = updater.summarize_changes(decisions)
        assert "f_2" in summary
        assert "f_3" not in summary

    def test_summary_parts_joined_with_period(self, updater):
        """Multiple parts are joined with '. '."""
        decisions = [
            MemoryDecision(MemoryAction.ADD, "name", "Minh"),
            MemoryDecision(MemoryAction.UPDATE, "role", "GV", old_value="SV"),
        ]
        summary = updater.summarize_changes(decisions)
        assert ". " in summary


# ---------------------------------------------------------------------------
# 20. _values_match edge cases
# ---------------------------------------------------------------------------

class TestValuesMatch:

    def test_exact_match(self, updater):
        assert updater._values_match("hello", "hello") is True

    def test_case_insensitive(self, updater):
        assert updater._values_match("Hello", "hello") is True

    def test_whitespace_stripped(self, updater):
        assert updater._values_match("  hello  ", "hello") is True

    def test_both_whitespace_and_case(self, updater):
        assert updater._values_match("  HELLO  ", "  hello  ") is True

    def test_different_values(self, updater):
        assert updater._values_match("hello", "world") is False

    def test_empty_strings(self, updater):
        assert updater._values_match("", "") is True

    def test_whitespace_only_vs_empty(self, updater):
        assert updater._values_match("   ", "") is True

    def test_vietnamese_text(self, updater):
        assert updater._values_match("Sài Gòn", "sài gòn") is True


# ---------------------------------------------------------------------------
# 21. MemoryDecision repr
# ---------------------------------------------------------------------------

class TestMemoryDecisionRepr:

    def test_repr_format(self):
        d = MemoryDecision(MemoryAction.ADD, "name", "Minh")
        r = repr(d)
        assert r == "MemoryDecision(add, name='Minh')"

    def test_repr_update(self):
        d = MemoryDecision(MemoryAction.UPDATE, "role", "GV", old_value="SV")
        r = repr(d)
        assert r == "MemoryDecision(update, role='GV')"

    def test_repr_delete(self):
        d = MemoryDecision(MemoryAction.DELETE, "loc", "không còn")
        r = repr(d)
        assert r == "MemoryDecision(delete, loc='không còn')"


# ---------------------------------------------------------------------------
# 22. classify confidence passthrough
# ---------------------------------------------------------------------------

class TestConfidencePassthrough:

    def test_add_confidence(self, updater):
        """Confidence is passed through to ADD decision."""
        result = updater.classify("name", "Minh", {}, confidence=0.75)
        assert result.confidence == 0.75

    def test_update_confidence(self, updater):
        """Confidence is passed through to UPDATE decision."""
        result = updater.classify("name", "Lan", {"name": "Minh"}, confidence=0.82)
        assert result.confidence == 0.82

    def test_delete_confidence(self, updater):
        """Confidence is passed through to DELETE decision."""
        result = updater.classify(
            "name", "không còn", {"name": "Minh"}, confidence=0.6
        )
        assert result.confidence == 0.6

    def test_noop_confidence(self, updater):
        """Confidence is passed through to NOOP decision."""
        result = updater.classify("name", "Minh", {"name": "Minh"}, confidence=0.99)
        assert result.confidence == 0.99

    def test_default_confidence(self, updater):
        """Default confidence is 0.9."""
        result = updater.classify("name", "Minh", {})
        assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# 23. Multiple UPDATEs to same type in batch
# ---------------------------------------------------------------------------

class TestBatchMultipleUpdates:

    def test_multiple_updates_same_type(self, updater):
        """Multiple facts with the same type in batch are each classified independently.

        The classify_batch does NOT update existing_facts between iterations,
        so both will be classified against the original existing_facts.
        """
        existing = {"name": "A"}
        extracted = [
            {"fact_type": "name", "value": "B", "confidence": 0.9},
            {"fact_type": "name", "value": "C", "confidence": 0.8},
        ]
        decisions = updater.classify_batch(extracted, existing)
        assert len(decisions) == 2
        # Both compare against original "A", so both are UPDATE
        assert decisions[0].action == MemoryAction.UPDATE
        assert decisions[0].new_value == "B"
        assert decisions[0].old_value == "A"
        assert decisions[1].action == MemoryAction.UPDATE
        assert decisions[1].new_value == "C"
        assert decisions[1].old_value == "A"


# ---------------------------------------------------------------------------
# 24. build_revision_metadata edge case — revision_history as string
# ---------------------------------------------------------------------------

class TestRevisionHistoryEdgeCases:

    def test_revision_history_json_string(self, updater):
        """revision_history stored as JSON string is correctly parsed."""
        history_list = [{"old": "v1", "new": "v2", "at": "2026-01-10T00:00:00+00:00"}]
        existing_meta = {
            "first_seen": "2026-01-01T00:00:00+00:00",
            "revision_history": json.dumps(history_list),
        }
        decision = MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type="status",
            new_value="v3",
            old_value="v2",
        )
        meta = updater.build_revision_metadata(decision, existing_metadata=existing_meta)
        assert isinstance(meta["revision_history"], list)
        assert len(meta["revision_history"]) == 2
        assert meta["revision_history"][-1]["new"] == "v3"


# ---------------------------------------------------------------------------
# Additional edge cases and MemoryAction enum tests
# ---------------------------------------------------------------------------

class TestMemoryActionEnum:

    def test_action_values(self):
        """MemoryAction enum has correct string values."""
        assert MemoryAction.ADD.value == "add"
        assert MemoryAction.UPDATE.value == "update"
        assert MemoryAction.DELETE.value == "delete"
        assert MemoryAction.NOOP.value == "noop"

    def test_action_is_str(self):
        """MemoryAction inherits from str."""
        assert isinstance(MemoryAction.ADD, str)
        assert MemoryAction.ADD == "add"


class TestMemoryDecisionSlots:

    def test_slots_defined(self):
        """MemoryDecision uses __slots__ for memory efficiency."""
        d = MemoryDecision(MemoryAction.ADD, "name", "test")
        assert hasattr(d, "__slots__")
        with pytest.raises(AttributeError):
            d.nonexistent_attr = "should fail"


class TestCustomThreshold:

    def test_custom_threshold_stored(self, updater_custom_threshold):
        """Custom similarity_threshold is stored correctly."""
        assert updater_custom_threshold._sim_threshold == 0.85


class TestBuildRevisionMetadataDelete:

    def test_delete_metadata_minimal(self, updater):
        """DELETE action: metadata contains fact_type and confidence but no revision_history append."""
        decision = MemoryDecision(
            action=MemoryAction.DELETE,
            fact_type="location",
            new_value="không còn",
            old_value="SG",
            confidence=0.7,
        )
        meta = updater.build_revision_metadata(decision)
        assert meta["fact_type"] == "location"
        assert meta["confidence"] == 0.7
        # DELETE does not add first_seen or revision_history
        assert "revision_history" not in meta
        assert "access_count" not in meta


class TestBuildRevisionMetadataNoop:

    def test_noop_metadata_minimal(self, updater):
        """NOOP action: metadata contains only fact_type and confidence."""
        decision = MemoryDecision(
            action=MemoryAction.NOOP,
            fact_type="name",
            new_value="Minh",
            old_value="Minh",
            confidence=0.95,
        )
        meta = updater.build_revision_metadata(decision)
        assert meta["fact_type"] == "name"
        assert meta["confidence"] == 0.95
        assert "first_seen" not in meta
        assert "revision_history" not in meta
