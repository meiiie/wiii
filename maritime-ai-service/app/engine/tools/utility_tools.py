"""
Utility Tools - General-purpose tools for AI agents.

SOTA 2026: Agents need basic utilities beyond domain-specific tools.
These tools provide calculation, datetime, and unit conversion capabilities.
"""

import ast
import logging
import math
import operator
from datetime import datetime, timezone, timedelta

from langchain_core.tools import tool

from app.engine.tools.registry import (
    ToolCategory,
    ToolAccess,
    get_tool_registry,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Safe Math Evaluator (no eval/exec — AST-based)
# =============================================================================

# Allowed math operators
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Allowed math functions
_SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
    "pi": math.pi,
    "e": math.e,
    # Nautical/domain-useful
    "radians": math.radians,
    "degrees": math.degrees,
}


def _safe_eval(node):
    """Safely evaluate an AST node (no arbitrary code execution)."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        # Guard against huge exponents
        if op_type == ast.Pow and isinstance(right, (int, float)) and abs(right) > 1000:
            raise ValueError("Exponent too large")
        return _SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_OPERATORS[op_type](_safe_eval(node.operand))
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCTIONS:
            func = _SAFE_FUNCTIONS[node.func.id]
            args = [_safe_eval(arg) for arg in node.args]
            if callable(func):
                return func(*args)
            return func  # Constants like pi, e
        raise ValueError(f"Unsupported function: {getattr(node.func, 'id', '?')}")
    elif isinstance(node, ast.Name):
        if node.id in _SAFE_FUNCTIONS:
            val = _SAFE_FUNCTIONS[node.id]
            if not callable(val):
                return val  # Constants like pi, e
        raise ValueError(f"Unknown variable: {node.id}")
    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


@tool(description="Tính toán biểu thức toán học. Hỗ trợ: +, -, *, /, **, sqrt, sin, cos, log, pi. Ví dụ: '15 * 1.852' (hải lý sang km), 'sqrt(3**2 + 4**2)'")
def tool_calculator(expression: str) -> str:
    """Calculate a math expression safely."""
    try:
        # Parse the expression into AST
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)

        # Format result
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                formatted = str(int(result))
            else:
                formatted = f"{result:.6g}"
        else:
            formatted = str(result)

        logger.info("[CALC] %s = %s", expression, formatted)
        return f"{expression} = {formatted}"

    except ZeroDivisionError:
        return "Lỗi: Chia cho 0"
    except (ValueError, TypeError, SyntaxError) as e:
        return f"Lỗi biểu thức: {e}"
    except Exception as e:
        logger.warning("Calculator error: %s", e)
        return f"Không thể tính: {e}"


@tool(description="Lấy ngày giờ hiện tại (UTC+7 Việt Nam). Hữu ích khi cần biết thời gian hiện tại, ngày hết hạn, thời hạn.")
def tool_current_datetime() -> str:
    """Get current date and time in Vietnam timezone (UTC+7)."""
    vn_tz = timezone(timedelta(hours=7))
    now = datetime.now(vn_tz)

    return (
        f"Ngày giờ hiện tại (UTC+7): {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Ngày: {now.strftime('%d/%m/%Y')}\n"
        f"Thứ: {['Hai', 'Ba', 'Tư', 'Năm', 'Sáu', 'Bảy', 'Chủ nhật'][now.weekday()]}\n"
        f"Giờ: {now.strftime('%H:%M')}"
    )


# =============================================================================
# Initialization
# =============================================================================

def init_utility_tools():
    """Register utility tools with the global registry."""
    registry = get_tool_registry()

    registry.register(
        tool_calculator,
        category=ToolCategory.UTILITY,
        access=ToolAccess.READ,
        description="Safe math calculator"
    )

    registry.register(
        tool_current_datetime,
        category=ToolCategory.UTILITY,
        access=ToolAccess.READ,
        description="Current date/time in Vietnam"
    )

    logger.info("Utility tools registered: calculator, current_datetime")
