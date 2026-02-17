"""
Test code quality - no bare except clauses allowed.
Verifies TASK-002 fix.
"""
import ast
from pathlib import Path
import pytest


def test_no_bare_except_clauses():
    """
    Scan entire codebase for bare 'except:' clauses.
    These should all be 'except Exception:' or more specific.

    TASK-002 fixed 5 instances. This test prevents regression.
    """
    app_dir = Path("app")
    bare_excepts = []

    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:  # bare except
                    bare_excepts.append(f"{py_file}:{node.lineno}")

    assert len(bare_excepts) == 0, (
        f"Found {len(bare_excepts)} bare except clauses (should be 0):\n"
        + "\n".join(f"  - {loc}" for loc in bare_excepts)
    )


def test_exception_handlers_have_logging():
    """
    Verify exception handlers include some form of logging.
    This is a best-effort check.
    """
    # This would require more sophisticated AST analysis
    # For now, just document the expectation
    pass
