# Design Document: Humanization & Stability

## Overview

Spec này tập trung vào việc fix bugs và cải thiện các component Memory hiện có để Bot nói chuyện tự nhiên hơn. Không tạo tool mới, chỉ sửa và tối ưu code hiện tại.

**Mục tiêu chính:**
1. Fix bug `MemorySummarizer.get_summary_async()` không tồn tại
2. Đảm bảo Memory flow hoạt động end-to-end
3. Cải thiện context retrieval cho follow-up questions
4. Tích hợp Anti-Repetition vào response generation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ChatService                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │PromptLoader │  │MemorySumm.  │  │  SemanticMemory     │  │
│  │(YAML Config)│  │(Tiered Mem) │  │  (pgvector+Gemini)  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │    UnifiedAgent       │                       │
│              │  (System Prompt +     │                       │
│              │   Context + History)  │                       │
│              └───────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. MemorySummarizer (Fix Required)

**Current Issue:** `chat_service.py` calls `get_summary_async()` but this method doesn't exist.

**Fix:** Add missing method to MemorySummarizer class.

```python
async def get_summary_async(self, session_id: str) -> Optional[str]:
    """
    Get formatted summary for a session (async).
    
    Returns:
        Formatted context string or None if no summaries
    """
    state = self.get_state(session_id)
    if not state.summaries:
        return None
    return state.get_context_for_prompt()
```

### 2. ChatService Integration Points

**Current Flow:**
1. `process_message()` → retrieves semantic context
2. Calls `_memory_summarizer.get_summary_async()` ❌ (broken)
3. Passes to UnifiedAgent

**Fixed Flow:**
1. `process_message()` → retrieves semantic context
2. Calls `_memory_summarizer.get_summary_async()` ✅ (fixed)
3. Combines with user_facts from SemanticMemory
4. Passes complete context to UnifiedAgent

### 3. TieredMemoryState Enhancement

```python
@dataclass
class TieredMemoryState:
    raw_messages: List[Dict[str, str]]  # Last 6-10 messages
    summaries: List[ConversationSummary]  # Compressed older context
    user_facts: List[str]  # Long-term facts from SemanticMemory
    total_messages_processed: int
    
    def get_context_for_prompt(self, max_raw: int = 6) -> str:
        """Build context string combining all tiers."""
```

## Data Models

### ConversationSummary
```python
@dataclass
class ConversationSummary:
    summary_text: str
    message_count: int
    topics: List[str]
    user_state: Optional[str]  # "mệt", "đói", "vui"
    created_at: datetime
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Memory Summarization Trigger
*For any* conversation with more than 10 messages, the MemorySummarizer SHALL trigger summarization and reduce raw_messages count to 6 or fewer.
**Validates: Requirements 1.1**

### Property 2: User State Preservation
*For any* conversation where user expresses emotional state (mệt, đói, buồn), the summary SHALL contain that state in user_state field.
**Validates: Requirements 1.2**

### Property 3: Name Extraction Accuracy
*For any* message containing Vietnamese name introduction patterns, the extracted name SHALL be a valid Vietnamese name (not common words like "là", "tôi").
**Validates: Requirements 2.1**

### Property 4: Name Usage Frequency
*For any* session with known user name, the name SHALL appear in 20-30% of responses (not every response, not never).
**Validates: Requirements 2.3**

### Property 5: No Greeting Repetition
*For any* follow-up message (not first in session), the response SHALL NOT start with greeting phrases like "Chào bạn", "Xin chào".
**Validates: Requirements 3.1**

### Property 6: Opening Phrase Variation
*For any* 4 consecutive responses in a session, at least 3 different opening phrases SHALL be used.
**Validates: Requirements 3.2, 3.3**

### Property 7: Context Retrieval for Follow-ups
*For any* follow-up question referencing previous context, the response SHALL demonstrate understanding of that context.
**Validates: Requirements 5.1**

### Property 8: Pronoun Detection Accuracy
*For any* message containing Vietnamese pronoun patterns (mình/cậu, tớ/cậu, anh/em, chị/em), the system SHALL correctly detect and store the pronoun style.
**Validates: Requirements 6.1**

### Property 9: Pronoun Adaptation Consistency
*For any* session with detected pronoun style, all subsequent AI responses SHALL use the adapted pronouns consistently (not mixing with default "tôi/bạn").
**Validates: Requirements 6.2**

### Property 10: Inappropriate Pronoun Filtering
*For any* detected pronoun containing vulgar or inappropriate terms, the system SHALL reject it and maintain default "tôi/bạn".
**Validates: Requirements 6.4**

## Error Handling

- If MemorySummarizer LLM fails → fallback to trimming old messages
- If SemanticMemory unavailable → use only ChatHistory sliding window
- If name extraction fails → continue without personalization

## Testing Strategy

### Property-Based Testing (Hypothesis)
- Test summarization trigger threshold
- Test name extraction patterns
- Test opening phrase variation

### Integration Testing
- End-to-end conversation flow with real services
- Memory persistence across simulated sessions
- Context retrieval accuracy
