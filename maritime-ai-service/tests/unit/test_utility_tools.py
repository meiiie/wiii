"""
Unit tests for Utility Tools (calculator, datetime).

Tests:
- tool_calculator: basic ops, functions, constants, edge cases
- tool_current_datetime: format, UTC+7, Vietnamese day names
"""

import math
import pytest

from app.engine.tools.utility_tools import tool_calculator, tool_current_datetime


# =============================================================================
# Tests: Calculator
# =============================================================================

class TestCalculator:
    def test_addition(self):
        result = tool_calculator.invoke("2 + 3")
        assert "= 5" in result

    def test_subtraction(self):
        result = tool_calculator.invoke("10 - 4")
        assert "= 6" in result

    def test_multiplication(self):
        result = tool_calculator.invoke("6 * 7")
        assert "= 42" in result

    def test_division(self):
        result = tool_calculator.invoke("15 / 3")
        assert "= 5" in result

    def test_float_division(self):
        result = tool_calculator.invoke("10 / 3")
        assert "3.33333" in result

    def test_power(self):
        result = tool_calculator.invoke("2 ** 10")
        assert "= 1024" in result

    def test_floor_division(self):
        result = tool_calculator.invoke("17 // 3")
        assert "= 5" in result

    def test_modulo(self):
        result = tool_calculator.invoke("17 % 5")
        assert "= 2" in result

    def test_negative_number(self):
        result = tool_calculator.invoke("-5 + 3")
        assert "= -2" in result

    # Functions
    def test_sqrt(self):
        result = tool_calculator.invoke("sqrt(16)")
        assert "= 4" in result

    def test_sin(self):
        result = tool_calculator.invoke("sin(0)")
        assert "= 0" in result

    def test_cos(self):
        result = tool_calculator.invoke("cos(0)")
        assert "= 1" in result

    def test_log(self):
        result = tool_calculator.invoke("log(1)")
        assert "= 0" in result

    def test_abs(self):
        result = tool_calculator.invoke("abs(-42)")
        assert "= 42" in result

    def test_round(self):
        result = tool_calculator.invoke("round(3.7)")
        assert "= 4" in result

    # Constants
    def test_pi(self):
        result = tool_calculator.invoke("pi")
        assert "3.14159" in result

    def test_e(self):
        result = tool_calculator.invoke("e")
        assert "2.71828" in result

    # Complex expressions
    def test_complex_expression(self):
        result = tool_calculator.invoke("sqrt(3**2 + 4**2)")
        assert "= 5" in result

    def test_nautical_miles_to_km(self):
        result = tool_calculator.invoke("15 * 1.852")
        assert "27.78" in result

    # Edge cases
    def test_division_by_zero(self):
        result = tool_calculator.invoke("1 / 0")
        assert "Chia cho 0" in result

    def test_large_exponent_rejected(self):
        result = tool_calculator.invoke("2 ** 10000")
        assert "Exponent too large" in result or "Lỗi" in result

    def test_invalid_expression(self):
        result = tool_calculator.invoke("not a math expression")
        assert "Lỗi" in result or "Không thể tính" in result

    def test_empty_expression(self):
        result = tool_calculator.invoke("")
        assert "Lỗi" in result or "Không thể tính" in result

    def test_unsafe_function_rejected(self):
        result = tool_calculator.invoke("__import__('os').system('ls')")
        assert "Lỗi" in result or "Unsupported" in result or "Không thể tính" in result

    def test_exec_rejected(self):
        result = tool_calculator.invoke("exec('print(1)')")
        assert "Lỗi" in result or "Unsupported" in result or "Không thể tính" in result


# =============================================================================
# Tests: DateTime
# =============================================================================

class TestCurrentDatetime:
    def test_returns_string(self):
        result = tool_current_datetime.invoke("")
        assert isinstance(result, str)

    def test_contains_utc7(self):
        result = tool_current_datetime.invoke("")
        assert "UTC+7" in result

    def test_contains_date_format(self):
        result = tool_current_datetime.invoke("")
        # Should contain date in dd/mm/yyyy format
        assert "/" in result
        assert "Ngày:" in result

    def test_contains_time(self):
        result = tool_current_datetime.invoke("")
        assert "Giờ:" in result

    def test_contains_day_of_week(self):
        result = tool_current_datetime.invoke("")
        assert "Thứ:" in result or "Chủ nhật" in result

    def test_vietnamese_day_names(self):
        """Vietnamese day names should be one of the expected values."""
        result = tool_current_datetime.invoke("")
        expected_days = ["Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Chủ nhật"]
        assert any(day in result for day in expected_days)
