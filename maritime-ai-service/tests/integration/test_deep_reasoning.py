"""
Test Deep Reasoning implementation
"""
import sys
sys.path.insert(0, '.')

from dataclasses import dataclass
from app.engine.conversation_analyzer import ConversationAnalyzer, get_conversation_analyzer

@dataclass
class MockMessage:
    role: str
    content: str

def test_conversation_analyzer():
    print("=" * 60)
    print("TEST: ConversationAnalyzer - Deep Reasoning")
    print("=" * 60)

    analyzer = get_conversation_analyzer()

    # Test 1: Detect incomplete explanation with "dau tien"
    print("\n[Test 1] Incomplete explanation detection")
    messages = [
        MockMessage('user', 'Rule 15 la gi?'),
        MockMessage('assistant', 'Rule 15 quy dinh ve tinh huong cat huong. Dau tien, tau nhuong duong phai tranh cat mui tau duoc nhuong duong.'),
        MockMessage('user', 'Thoi tiet hom nay the nao?'),
    ]

    context = analyzer.analyze(messages)
    print(f"  Last topic: {context.last_explanation_topic}")
    print(f"  Should offer continuation: {context.should_offer_continuation}")

    # Test 2: Build proactive context
    print("\n[Test 2] Proactive context building")
    proactive = analyzer.build_proactive_context(context)
    if proactive:
        print(f"  Proactive hint generated: YES")
        print(f"  Content: {proactive[:150]}...")
    else:
        print(f"  Proactive hint generated: NO")

    # Test 3: Topic extraction
    print("\n[Test 3] Topic extraction")
    test_contents = [
        "Rule 15 quy dinh ve tinh huong cat huong",
        "Theo COLREGs, tau phai...",
        "SOLAS yeu cau tau phai co...",
        "Dieu 25 cua Bo luat Hang hai",
    ]
    for content in test_contents:
        topic = analyzer.extract_topic(content)
        print(f"  '{content[:40]}...' -> Topic: {topic}")

    # Test 4: Continuation request detection
    print("\n[Test 4] Continuation request detection")
    test_cases = [
        ("tiep tuc di", "Rule 15", True),
        ("noi them ve Rule 15", "Rule 15", True),
        ("thoi tiet hom nay the nao?", "Rule 15", False),
        ("chi tiet hon duoc khong?", "SOLAS", True),
    ]
    for user_msg, topic, expected in test_cases:
        result = analyzer.is_continuation_request(user_msg, topic)
        status = "[OK]" if result == expected else "[FAIL]"
        print(f"  {status} '{user_msg}' (topic: {topic}) -> {result}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_conversation_analyzer()
