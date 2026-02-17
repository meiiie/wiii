# Design Document: Memory Isolation & Context Protection

## Overview

Thiết kế hệ thống để đảm bảo blocked messages không làm "nhiễm độc" AI context và Vector DB. Hệ thống sẽ:
1. Lưu blocked messages vào DB với cờ đánh dấu (cho Admin review)
2. Lọc blocked messages khỏi context window khi gọi LLM
3. Không lưu blocked content vào Semantic Memory (Vector DB)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE FLOW WITH ISOLATION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User Message                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────┐                                                        │
│   │ Guardian Agent  │                                                        │
│   │ (Content Check) │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│     ┌──────┴──────┐                                                          │
│     │             │                                                          │
│     ▼             ▼                                                          │
│  BLOCKED       ALLOWED                                                       │
│     │             │                                                          │
│     │             ├──────────────────────────────────────┐                   │
│     │             │                                      │                   │
│     ▼             ▼                                      ▼                   │
│  ┌──────────┐  ┌──────────┐                      ┌──────────────┐            │
│  │ Save to  │  │ Save to  │                      │ Save to      │            │
│  │ chat_    │  │ chat_    │                      │ semantic_    │            │
│  │ history  │  │ history  │                      │ memories     │            │
│  │ is_block │  │ is_block │                      │ (Vector DB)  │            │
│  │ = TRUE   │  │ = FALSE  │                      └──────────────┘            │
│  └──────────┘  └──────────┘                                                  │
│       │             │                                                        │
│       │             ▼                                                        │
│       │        ┌──────────────┐                                              │
│       │        │ Get History  │                                              │
│       │        │ (Filter      │                                              │
│       │        │ is_blocked)  │                                              │
│       │        └──────┬───────┘                                              │
│       │               │                                                      │
│       │               ▼                                                      │
│       │        ┌──────────────┐                                              │
│       │        │ Build Context│                                              │
│       │        │ (Clean)      │                                              │
│       │        └──────┬───────┘                                              │
│       │               │                                                      │
│       │               ▼                                                      │
│       │        ┌──────────────┐                                              │
│       │        │ Call Gemini  │                                              │
│       │        │ (No toxic    │                                              │
│       │        │  content)    │                                              │
│       │        └──────────────┘                                              │
│       │                                                                      │
│       ▼                                                                      │
│  Return Blocked                                                              │
│  Response                                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Database Schema Changes

```sql
-- Add columns to chat_history table
ALTER TABLE chat_history 
ADD COLUMN is_blocked BOOLEAN DEFAULT FALSE,
ADD COLUMN block_reason TEXT;

-- Create index for efficient filtering
CREATE INDEX idx_chat_history_is_blocked ON chat_history(is_blocked);
```

### 2. ChatHistoryRepository Updates

```python
class ChatHistoryRepository:
    def save_message(
        self, 
        session_id: UUID, 
        role: str, 
        content: str,
        is_blocked: bool = False,
        block_reason: Optional[str] = None
    ) -> None:
        """Save message with optional blocked flag."""
        
    def get_recent_messages(
        self, 
        session_id: UUID, 
        limit: int = 10,
        include_blocked: bool = False  # Default: exclude blocked
    ) -> List[ChatMessage]:
        """Get recent messages, filtering blocked by default."""
```

### 3. ChatService Updates

```python
class ChatService:
    async def process_message(self, request, background_save):
        # Step 1: Guardian validation
        guardian_decision = await self._guardian_agent.validate_message(message)
        
        if guardian_decision.action == "BLOCK":
            # Save blocked message to DB (for admin review)
            self._chat_history.save_message(
                session_id=session_id,
                role="user",
                content=message,
                is_blocked=True,
                block_reason=guardian_decision.reason
            )
            # DO NOT save to semantic memory
            return self._create_blocked_response(...)
        
        # Step 2: Get clean history (exclude blocked)
        recent_messages = self._chat_history.get_recent_messages(
            session_id, 
            include_blocked=False  # Clean context
        )
        
        # Step 3: Process normally...
        # Step 4: Save to semantic memory (only for valid messages)
```

## Data Models

### ChatMessage (Updated)

```python
@dataclass
class ChatMessage:
    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime
    is_blocked: bool = False
    block_reason: Optional[str] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Blocked Messages Never Enter Context

*For any* blocked message, when building LLM context, the message content SHALL NOT appear in the conversation_history string sent to Gemini.

**Validates: Requirements 2.1, 2.2**

### Property 2: Blocked Messages Never Enter Vector DB

*For any* blocked message, the semantic_memories table SHALL NOT contain any record with that message content.

**Validates: Requirements 3.1, 3.2**

### Property 3: Blocked Messages Are Logged

*For any* blocked message, the chat_history table SHALL contain a record with is_blocked = true and the original content preserved.

**Validates: Requirements 1.1, 4.1**

### Property 4: Clean Messages Flow Normally

*For any* non-blocked message, the message SHALL be saved to both chat_history (is_blocked = false) and semantic_memories.

**Validates: Requirements 1.4, 3.4**

## Error Handling

1. **Database Error on Blocked Save**: Log error, still return blocked response to user
2. **Schema Migration Failure**: Fallback to current behavior (no is_blocked column)
3. **Filter Query Failure**: Log error, return empty history (safe default)

## Testing Strategy

### Unit Tests
- Test save_message with is_blocked=True
- Test get_recent_messages with include_blocked=False
- Test context building excludes blocked messages

### Property-Based Tests
- Generate random message sequences with some blocked
- Verify blocked messages never appear in context
- Verify blocked messages never appear in Vector DB

### Integration Tests
- End-to-end test: Send blocked message, verify not in next context
- Admin API test: Verify blocked messages visible to admin
