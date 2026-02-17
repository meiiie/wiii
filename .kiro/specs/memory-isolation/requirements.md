# Requirements Document: Memory Isolation & Context Protection

## Introduction

Hệ thống cần đảm bảo rằng các tin nhắn vi phạm (bị BLOCK bởi Guardian Agent) không làm "nhiễm độc" bộ nhớ của AI. Điều này bao gồm:
- Không lưu blocked content vào Vector DB (Semantic Memory)
- Không đưa blocked messages vào Context Window khi gọi LLM
- Vẫn lưu log để Admin review nhưng đánh dấu rõ ràng

## Glossary

- **Blocked Message**: Tin nhắn bị Guardian Agent hoặc Guardrails chặn do vi phạm nội dung
- **Vector DB**: PostgreSQL với pgvector extension, lưu Semantic Memory
- **Context Window**: Lịch sử hội thoại được gửi cho Gemini để tạo response
- **Chat History**: Bảng lưu lịch sử chat trong PostgreSQL (chat_history)
- **Semantic Memory**: Bộ nhớ ngữ nghĩa dài hạn (semantic_memories table)

## Requirements

### Requirement 1: Blocked Message Flagging

**User Story:** As a system administrator, I want blocked messages to be flagged in the database, so that I can review violations while keeping the AI context clean.

#### Acceptance Criteria

1. WHEN a message is blocked by Guardian Agent THEN the System SHALL save the message to chat_history with is_blocked = true
2. WHEN a message is blocked THEN the System SHALL NOT save the message to semantic_memories table (Vector DB)
3. WHEN saving a blocked message THEN the System SHALL include the block_reason in the database record
4. WHEN a message passes validation THEN the System SHALL save it with is_blocked = false (default)

### Requirement 2: Context Window Protection

**User Story:** As an AI system, I want to never see blocked messages in my context, so that my responses remain clean and professional.

#### Acceptance Criteria

1. WHEN retrieving chat history for LLM context THEN the System SHALL filter out all messages with is_blocked = true
2. WHEN building conversation_history string THEN the System SHALL exclude blocked messages
3. WHEN counting recent messages for sliding window THEN the System SHALL only count non-blocked messages
4. WHEN a user sends multiple blocked messages THEN the System SHALL maintain session but exclude all blocked content from context

### Requirement 3: Semantic Memory Protection

**User Story:** As a data engineer, I want blocked content to never enter the Vector DB, so that future AI training data remains clean.

#### Acceptance Criteria

1. WHEN a message is blocked THEN the System SHALL skip the semantic memory storage step entirely
2. WHEN processing a blocked message THEN the System SHALL NOT call store_interaction() on SemanticMemoryEngine
3. WHEN a message is flagged (not blocked) THEN the System SHALL still store it to semantic memory with a flag
4. IF semantic memory storage fails for a valid message THEN the System SHALL log the error but continue processing

### Requirement 4: Admin Visibility

**User Story:** As an administrator, I want to see all blocked messages with reasons, so that I can monitor user behavior and improve the system.

#### Acceptance Criteria

1. WHEN querying chat history for admin review THEN the System SHALL include blocked messages with their block_reason
2. WHEN displaying blocked messages to admin THEN the System SHALL show timestamp, user_id, content, and block_reason
3. WHEN a user has multiple violations THEN the System SHALL allow admin to see violation history

### Requirement 5: Database Schema Update

**User Story:** As a developer, I want the chat_history table to support blocked message tracking, so that the system can properly isolate toxic content.

#### Acceptance Criteria

1. THE chat_history table SHALL have an is_blocked column of type BOOLEAN with default FALSE
2. THE chat_history table SHALL have a block_reason column of type TEXT (nullable)
3. WHEN migrating existing data THEN the System SHALL set is_blocked = false for all existing records
4. THE System SHALL create an index on is_blocked column for efficient filtering
