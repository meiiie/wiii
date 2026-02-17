"""
Test script for EnhancedPromptLoader (Task 1.2)
Validates: Requirements 1.2, 7.1, 7.3
"""

import sys
sys.path.insert(0, '.')

from app.prompts.prompt_loader import PromptLoader, get_prompt_loader


def test_basic_prompt():
    """Test basic build_system_prompt works."""
    print("=== Test 1: Basic prompt ===")
    loader = PromptLoader()
    prompt = loader.build_system_prompt('student')
    assert prompt is not None
    assert len(prompt) > 100
    print("[OK] Basic prompt generated successfully")
    return True


def test_name_usage_control():
    """Test name usage frequency control (20-30%)."""
    print("\n=== Test 2: Name usage control ===")
    loader = PromptLoader()

    # Case 1: Low usage (< 20%) - should suggest using name
    prompt_low = loader.build_system_prompt(
        role='student',
        user_name='Hung',
        name_usage_count=1,
        total_responses=10
    )
    assert 'Co the dung ten' in prompt_low or 'Có thể dùng tên' in prompt_low, "Should suggest using name when ratio < 20%"
    print("  [OK] Low usage: suggests using name")

    # Case 2: High usage (>= 30%) - should NOT use name
    prompt_high = loader.build_system_prompt(
        role='student',
        user_name='Hung',
        name_usage_count=4,
        total_responses=10
    )
    assert 'KHONG dung ten' in prompt_high or 'KHÔNG dùng tên' in prompt_high, "Should NOT use name when ratio >= 30%"
    print("  [OK] High usage: prevents using name")

    return True


def test_singleton():
    """Test get_prompt_loader singleton."""
    print("\n=== Test 3: Singleton pattern ===")
    loader1 = get_prompt_loader()
    loader2 = get_prompt_loader()
    assert loader1 is loader2, "Should return same instance"
    print("  [OK] Singleton works correctly")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing EnhancedPromptLoader (Task 1.2)")
    print("Validates: Requirements 1.2, 7.1, 7.3")
    print("=" * 60)

    tests = [
        test_basic_prompt,
        test_name_usage_control,
        test_singleton,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"  [FAIL] FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
