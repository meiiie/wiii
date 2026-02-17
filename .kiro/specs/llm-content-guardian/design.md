# Design Document: LLM Content Guardian

## Overview

Spec này nâng cấp hệ thống Guardrails hiện có bằng cách thêm LLM-based validation. Thay vì dựa vào hardcoded patterns, Guardian Agent sử dụng Gemini để:

1. **Validate custom pronoun requests** - Xử lý "gọi tôi là công chúa và bạn là trẫm"
2. **Detect inappropriate content contextually** - Phân biệt "cướp biển" trong ngữ cảnh hàng hải vs xúc phạm
3. **Fallback gracefully** - Dùng rule-based khi LLM không khả dụng

**Mục tiêu chính:**
- Linh hoạt hơn hardcoded patterns
- Giảm false positives (block nhầm)
- Hỗ trợ custom pronouns phức tạp
- Tối ưu chi phí LLM

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ChatService                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐     ┌──────────────────────────────────────┐  │
│  │  User Message    │────▶│         Guardian Agent               │  │
│  └──────────────────┘     │  ┌────────────────────────────────┐  │  │
│                           │  │  1. Quick Check (Rule-based)   │  │  │
│                           │  │     - Simple greetings: SKIP   │  │  │
│                           │  │     - Known patterns: CACHE    │  │  │
│                           │  └────────────────────────────────┘  │  │
│                           │              │                        │  │
│                           │              ▼                        │  │
│                           │  ┌────────────────────────────────┐  │  │
│                           │  │  2. LLM Validation (Gemini)    │  │  │
│                           │  │     - Pronoun requests         │  │  │
│                           │  │     - Inappropriate content    │  │  │
│                           │  │     - Contextual analysis      │  │  │
│                           │  └────────────────────────────────┘  │  │
│                           │              │                        │  │
│                           │              ▼                        │  │
│                           │  ┌────────────────────────────────┐  │  │
│                           │  │  3. Decision                   │  │  │
│                           │  │     - ALLOW + custom pronouns  │  │  │
│                           │  │     - BLOCK + reason           │  │  │
│                           │  │     - FLAG + review needed     │  │  │
│                           │  └────────────────────────────────┘  │  │
│                           └──────────────────────────────────────┘  │
│                                          │                           │
│                                          ▼                           │
│                           ┌──────────────────────────────────────┐  │
│                           │         UnifiedAgent                 │  │
│                           │  (with custom pronouns if approved)  │  │
│                           └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. GuardianAgent (New Component)

```python
class GuardianAgent:
    """
    LLM-based content moderation agent.
    
    CHỈ THỊ KỸ THUẬT SỐ 21: LLM Content Guardian
    """
    
    def __init__(self, llm=None, fallback_guardrails=None):
        self._llm = llm  # Gemini
        self._fallback = fallback_guardrails  # Current Guardrails
        self._cache = {}  # Decision cache
    
    async def validate_message(
        self,
        message: str,
        context: Optional[str] = None
    ) -> GuardianDecision:
        """
        Validate user message using LLM.
        
        Returns:
            GuardianDecision with action (ALLOW/BLOCK/FLAG) and details
        """
    
    async def validate_pronoun_request(
        self,
        message: str
    ) -> PronounValidationResult:
        """
        Validate custom pronoun request.
        
        Returns:
            PronounValidationResult with approved pronouns or rejection reason
        """
    
    def _should_skip_llm(self, message: str) -> bool:
        """Check if LLM validation can be skipped (simple greetings)."""
    
    def _get_cached_decision(self, message: str) -> Optional[GuardianDecision]:
        """Get cached decision for similar messages."""
```

### 2. GuardianDecision (Data Model)

```python
@dataclass
class GuardianDecision:
    action: Literal["ALLOW", "BLOCK", "FLAG"]
    reason: Optional[str] = None
    custom_pronouns: Optional[Dict[str, str]] = None
    confidence: float = 1.0
    used_llm: bool = False
    latency_ms: int = 0
```

### 3. PronounValidationResult (Data Model)

```python
@dataclass
class PronounValidationResult:
    approved: bool
    user_called: str  # How AI calls user
    ai_self: str  # How AI refers to itself
    rejection_reason: Optional[str] = None
```

### 4. Guardian Prompt Template

```python
GUARDIAN_PROMPT = """Bạn là Guardian Agent, chuyên kiểm tra nội dung tin nhắn.

NHIỆM VỤ: Phân tích tin nhắn sau và trả về JSON.

TIN NHẮN: "{message}"
NGỮ CẢNH: {context}

PHÂN TÍCH:
1. Có yêu cầu xưng hô đặc biệt không? (ví dụ: "gọi tôi là X")
2. Có nội dung tục tĩu/xúc phạm không?
3. Nếu có từ "nhạy cảm", có phù hợp với ngữ cảnh hàng hải không?

TRẢ VỀ JSON:
{
    "action": "ALLOW" | "BLOCK" | "FLAG",
    "reason": "lý do nếu BLOCK/FLAG",
    "pronoun_request": {
        "detected": true/false,
        "user_called": "cách gọi user",
        "ai_self": "cách AI tự xưng",
        "appropriate": true/false
    },
    "confidence": 0.0-1.0
}

CHÚ Ý:
- "cướp biển" trong ngữ cảnh hàng hải là OK
- "công chúa/hoàng tử" là roleplay OK
- Từ tục tĩu tiếng Việt: mày, tao, đ.m, vcl... là BLOCK
- Nếu không chắc chắn, dùng FLAG thay vì BLOCK
"""
```

## Data Models

### GuardianConfig
```python
@dataclass
class GuardianConfig:
    enable_llm: bool = True
    timeout_ms: int = 2000
    cache_ttl_seconds: int = 3600
    skip_patterns: List[str] = field(default_factory=list)  # Patterns to skip LLM
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Pronoun Request Validation
*For any* custom pronoun request, the Guardian_Agent SHALL return either approved pronouns (if appropriate) or default pronouns (if inappropriate), never null.
**Validates: Requirements 1.2, 1.3**

### Property 2: Contextual Content Filtering
*For any* message containing potentially inappropriate words, the Guardian_Agent SHALL consider context before blocking - maritime-related content with "dangerous" words SHALL be allowed.
**Validates: Requirements 2.2, 2.3**

### Property 3: Fallback Mechanism
*For any* LLM failure or timeout, the Guardian_Agent SHALL fallback to rule-based filtering and return a valid decision within 2 seconds.
**Validates: Requirements 3.1, 3.2**

### Property 4: Custom Pronoun Lifecycle
*For any* approved custom pronoun, the system SHALL store it in SessionState and use it in subsequent responses until changed or session ends.
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 5: LLM Skip Optimization
*For any* simple greeting message (chào, hello, hi), the Guardian_Agent SHALL skip LLM validation and return ALLOW immediately.
**Validates: Requirements 5.3**

### Property 6: Decision Caching
*For any* repeated message pattern within cache TTL, the Guardian_Agent SHALL return cached decision without calling LLM.
**Validates: Requirements 5.2**

## Error Handling

- If LLM fails → fallback to rule-based Guardrails
- If LLM timeout (>2s) → fallback to rule-based
- If JSON parsing fails → FLAG for review
- If pronoun validation fails → use default pronouns

## Testing Strategy

### Property-Based Testing (Hypothesis)
- Test pronoun request validation with random inputs
- Test contextual filtering with maritime vs non-maritime context
- Test fallback mechanism with simulated LLM failures
- Test caching with repeated messages

### Unit Testing
- Test Guardian prompt generation
- Test JSON response parsing
- Test cache hit/miss logic
- Test skip patterns matching

### Integration Testing
- End-to-end flow with real Gemini
- Latency measurements
- Cost tracking per request
