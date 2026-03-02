"""Sprint 222: Graph-level host context injection.

Tests for _inject_host_context() in graph.py — converts page_context (Sprint 221)
or host_context (Sprint 222) into a formatted prompt block at graph entry.
"""
import pytest


def test_inject_host_context_empty_when_no_context():
    """No page_context and no host_context -> empty string."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {"context": {}}
    result = _inject_host_context(state)
    assert result == ""


def test_inject_host_context_empty_when_context_missing():
    """Missing context key entirely -> empty string."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {}
    result = _inject_host_context(state)
    assert result == ""


def test_inject_host_context_from_legacy_page_context():
    """Legacy page_context should produce a formatted prompt."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "page_context": {
                "page_type": "lesson",
                "page_title": "COLREGs Rule 14",
                "course_name": "An toàn hàng hải",
            }
        }
    }
    result = _inject_host_context(state)
    assert "<host_context" in result
    assert "COLREGs Rule 14" in result
    assert "An toàn hàng hải" in result


def test_inject_host_context_from_new_schema():
    """New host_context dict should produce a formatted prompt."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "host_context": {
                "host_type": "ecommerce",
                "page": {"type": "product", "title": "Máy Bơm Shimizu"},
            }
        }
    }
    result = _inject_host_context(state)
    assert "<host_context" in result
    assert "Máy Bơm Shimizu" in result


def test_inject_host_context_new_schema_takes_priority():
    """When both host_context and page_context exist, host_context wins."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "host_context": {
                "host_type": "lms",
                "page": {"type": "quiz", "title": "New Quiz"},
            },
            "page_context": {
                "page_type": "lesson",
                "page_title": "Old Lesson",
            },
        }
    }
    result = _inject_host_context(state)
    assert "New Quiz" in result
    assert "Old Lesson" not in result


def test_inject_host_context_with_quiz_has_socratic():
    """Quiz page context should include Socratic warning."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "page_context": {
                "page_type": "quiz",
                "page_title": "Kiểm tra",
                "quiz_question": "Tàu nào nhường?",
            }
        }
    }
    result = _inject_host_context(state)
    # LMS adapter includes "KHÔNG cho đáp án trực tiếp" for quiz pages
    assert "KHÔNG" in result


def test_inject_host_context_graceful_on_bad_host_context():
    """Bad host_context data should not crash, just return empty."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "host_context": "not_a_dict"  # Invalid
        }
    }
    result = _inject_host_context(state)
    assert isinstance(result, str)  # Should not raise


def test_inject_host_context_graceful_on_bad_page_context():
    """Bad page_context data should not crash, just return empty."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "page_context": 12345  # Invalid
        }
    }
    result = _inject_host_context(state)
    assert isinstance(result, str)  # Should not raise


def test_inject_host_context_lms_host_type_from_legacy():
    """Legacy page_context always maps to host_type=lms."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "page_context": {
                "page_type": "dashboard",
                "page_title": "Trang chủ",
            }
        }
    }
    result = _inject_host_context(state)
    assert 'type="lms"' in result


def test_inject_host_context_with_student_state():
    """Legacy page_context with student_state should include user_state."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "page_context": {
                "page_type": "lesson",
                "page_title": "Bài 1",
            },
            "student_state": {
                "time_on_page_ms": 180000,  # 3 minutes
                "scroll_percent": 75.0,
            },
        }
    }
    result = _inject_host_context(state)
    assert "3 phút" in result
    assert "75%" in result


def test_inject_host_context_generic_host_type():
    """Unknown host_type should use generic adapter."""
    from app.engine.multi_agent.graph import _inject_host_context
    state = {
        "context": {
            "host_context": {
                "host_type": "crm",
                "page": {"type": "contact", "title": "Customer Details"},
            }
        }
    }
    result = _inject_host_context(state)
    assert "<host_context" in result
    assert "Customer Details" in result
    assert 'type="crm"' in result


def test_streaming_path_has_host_context_injection():
    """graph_streaming.py must call _inject_host_context or equivalent."""
    import inspect
    from app.engine.multi_agent import graph_streaming
    source = inspect.getsource(graph_streaming)
    assert "host_context_prompt" in source or "_inject_host_context" in source, (
        "Streaming path must inject host context (sync/stream parity)"
    )
