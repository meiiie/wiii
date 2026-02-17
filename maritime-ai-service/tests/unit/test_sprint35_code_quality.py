"""
Tests for Sprint 35: Code quality improvements.

Covers:
- datetime.utcnow() replaced with datetime.now(timezone.utc)
- except Exception: blocks have `as e` for debuggability
- test_pronoun_detection.py functions assert instead of return
"""

import ast
import pytest


class TestDatetimeUtcnowRemoved:
    """Verify no deprecated datetime.utcnow() calls remain in app/."""

    def test_no_utcnow_in_memory_summarizer(self):
        with open("app/engine/memory_summarizer.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert "utcnow()" not in content
        assert "timezone.utc" in content

    def test_no_utcnow_in_vision_processor(self):
        with open("app/services/vision_processor.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert "utcnow()" not in content
        assert "timezone.utc" in content


class TestExceptExceptionHasVariable:
    """Verify runtime except Exception blocks capture the exception."""

    @pytest.mark.parametrize("filepath", [
        "app/main.py",
        "app/repositories/thread_repository.py",
        "app/engine/multi_agent/supervisor.py",
        "app/repositories/neo4j_knowledge_repository.py",
        "app/engine/tools/code_execution_tools.py",
        "app/repositories/chat_history_repository.py",
        "app/engine/multi_agent/agents/tutor_node.py",
        "app/domains/base.py",
        "app/engine/agentic_rag/query_rewriter.py",
        "app/api/v1/admin.py",
    ])
    def test_except_exception_captures_variable(self, filepath):
        """All runtime except Exception blocks should use `as e`."""
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    continue  # bare except:, skip
                # Check if it's `except Exception`
                if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    # `node.name` is the `as e` variable — None means no variable
                    # Allow: import-guard patterns (body is just `pass` at module level)
                    # or circuit breaker patterns that re-raise
                    body_is_pass = (
                        len(node.body) == 1
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                    ) or (
                        len(node.body) == 1
                        and isinstance(node.body[0], ast.Pass)
                    )
                    body_is_raise = any(
                        isinstance(stmt, ast.Raise) for stmt in node.body
                    )
                    # If it's a simple pass (import guard) or re-raise, skip
                    if body_is_pass or body_is_raise:
                        continue
                    assert node.name is not None, (
                        f"{filepath}: `except Exception:` at line {node.lineno} "
                        f"should use `except Exception as e:`"
                    )


class TestPronounDetectionAsserts:
    """Verify test_pronoun_detection.py uses assert, not return."""

    def test_no_return_in_test_functions(self):
        with open("tests/unit/test_pronoun_detection.py", "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Check that the function body does not end with a Return
                last_stmt = node.body[-1] if node.body else None
                if isinstance(last_stmt, ast.Return) and last_stmt.value is not None:
                    pytest.fail(
                        f"test function '{node.name}' returns a value "
                        f"(line {last_stmt.lineno}) — should use assert"
                    )
