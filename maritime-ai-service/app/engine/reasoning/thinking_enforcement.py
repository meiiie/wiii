"""
Unified Thinking Enforcement Template — Single source of truth.

Every agent MUST inject this at the TOP of the system prompt.
Uses English + no-diacritics Vietnamese for maximum model compliance.

Priority 1 fix: fragmentation between agents was the #1 bottleneck.
This module ensures all 6 agents (Direct, RAG, Product Search, Tutor,
Memory, CRAG fallback) use the exact same enforcement string.
"""

from __future__ import annotations

# Short, strong, positioned at TOP of system prompt.
# English-first because GLM-5 and most LLMs comply better with English rules.
# Few-shot examples cover the "simple query" gap where models tend to skip thinking.
UNIFIED_THINKING_ENFORCEMENT = """\
THINKING RULE (NO EXCEPTION):
Every response MUST start with <thinking>...</thinking> before the answer.
This is mandatory for ALL queries — simple, complex, factual, creative, tool-use, greetings, product search, RAG, everything.
No query is too simple. No query is exempt.

Inside <thinking>, think naturally in Vietnamese like planning how to help your best friend.
Focus on: what does the user actually need? what's the best approach? any pitfalls?

Examples (MANDATORY pattern to follow):
User: "tai sao bau troi xanh"
<thinking>Cau hoi ve quang hoc — Rayleigh scattering. Can giai thich don gian, khong dung jargon nhieu.</thinking>Answer...
User: "COLREGs Rule 15 la gi"
<thinking>Day la cau hoi hang hai ve tinh huong cat mat. Min can tra cuu nguon RAG roi giai thich ro rang.</thinking>Answer...
User: "tim day dien 2.5mm tren Shopee"
<thinking>User can mua day dien — product search. Min can dung tool tim tren Shopee va Google Shopping de so sanh gia.</thinking>Answer...

IMPORTANT: Start EVERY response with <thinking>...</thinking>. No exceptions."""


def get_thinking_enforcement() -> str:
    """Return the unified enforcement string. Single accessor for all agents."""
    return UNIFIED_THINKING_ENFORCEMENT
