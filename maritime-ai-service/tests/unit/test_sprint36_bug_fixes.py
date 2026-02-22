"""
Tests for Sprint 36: Code bug fixes.

Covers:
- chat_history_repository.py uses .is_(False) not == False
- multimodal_ingestion_service.py open() uses encoding='utf-8'
- health.py readiness endpoint does not leak str(e)
- chat_stream.py SSE error does not leak str(e)
- evaluator.py does not leak str(e) in details
"""

import ast
import re
import pytest


class TestSQLAlchemyComparison:
    """Verify SQLAlchemy column comparisons use .is_(False) not == False."""

    def test_no_equality_false_in_repository(self):
        with open("app/repositories/chat_history_repository.py", "r", encoding="utf-8") as f:
            content = f.read()
        # Should NOT contain == False (Python equality, not SQLAlchemy)
        assert "== False" not in content, (
            "Use .is_(False) instead of == False for SQLAlchemy column comparisons"
        )

    def test_uses_is_false(self):
        with open("app/repositories/chat_history_repository.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert ".is_(False)" in content


class TestOpenEncodingSpecified:
    """Verify open() calls in ingestion service specify encoding."""

    def test_progress_file_read_has_encoding(self):
        with open("app/services/multimodal_ingestion_service.py", "r", encoding="utf-8") as f:
            content = f.read()
        # Find open() for progress_file read — should have encoding
        # Pattern: open(progress_file, 'r', encoding='utf-8')
        assert "encoding='utf-8'" in content or 'encoding="utf-8"' in content

    def test_no_text_open_without_encoding(self):
        """No text-mode open() without encoding in ingestion service."""
        with open("app/services/multimodal_ingestion_service.py", "r", encoding="utf-8") as f:
            content = f.read()
        # Find all open() calls with text mode
        # Pattern: open(..., 'r') or open(..., 'w') without encoding
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if 'open(' in stripped and ("'r'" in stripped or "'w'" in stripped):
                # Must also contain encoding=
                assert 'encoding' in stripped, (
                    f"Line {i}: open() in text mode without encoding: {stripped}"
                )


class TestNoStrEInHttpResponses:
    """Verify HTTP-facing code does not leak str(e) to clients."""

    def test_health_readiness_no_str_e(self):
        with open("app/api/v1/health.py", "r", encoding="utf-8") as f:
            content = f.read()
        # The readiness endpoint should not return str(e)
        # Look for "reason": str(e) pattern
        assert '"reason": str(e)' not in content
        assert "'reason': str(e)" not in content

    def test_chat_stream_sse_no_str_e(self):
        with open("app/api/v1/chat_stream.py", "r", encoding="utf-8") as f:
            content = f.read()
        # SSE error should not include str(e) in message
        assert '"message": str(e)' not in content
        assert "'message': str(e)" not in content

    def test_evaluator_no_str_e_in_details(self):
        """Evaluator module was removed (refactored into confidence_evaluator).
        Check the replacement file instead."""
        import os
        old_path = "app/engine/evaluation/evaluator.py"
        new_path = "app/engine/agentic_rag/confidence_evaluator.py"
        assert not os.path.exists(old_path), "Old evaluator.py should not exist"
        with open(new_path, "r", encoding="utf-8") as f:
            content = f.read()
        # EvaluationResult should not include str(e) in details
        assert '"error": str(e)' not in content
        assert "'error': str(e)" not in content
