# Requirements Document

## Introduction

Spec này tập trung vào **Giai đoạn 1: Humanization & Stability** theo khuyến nghị của Cố vấn Kiến trúc. Mục tiêu là làm cho Bot nói chuyện tự nhiên, nhớ tên, nhớ ngữ cảnh - giải quyết 90% phàn nàn của người dùng hiện tại.

**Phạm vi:** Chỉ cải thiện các component hiện có, KHÔNG tạo tool hay chức năng mới.

**Tham chiếu:** #[[file:Documents/phanhoi/phanhoi1.md]]

## Glossary

- **Maritime_AI_Service**: Hệ thống AI Tutor hỗ trợ học viên hàng hải
- **MemorySummarizer**: Component nén và tóm tắt lịch sử hội thoại dài
- **SemanticMemory**: Bộ nhớ ngữ nghĩa lưu trữ facts về user (pgvector + Gemini embeddings)
- **PromptLoader**: Component load persona configuration từ YAML files
- **TieredMemory**: Kiến trúc bộ nhớ 3 tầng (Raw → Summarized → Long-term Facts)
- **Anti-Repetition**: Cơ chế ngăn Bot lặp lại câu chào và cách mở đầu

## Requirements

### Requirement 1: Memory Summarizer Integration

**User Story:** As a user, I want the bot to remember what we discussed earlier in long conversations, so that I don't have to repeat context.

#### Acceptance Criteria

1. WHEN a conversation exceeds 10 messages THEN the Maritime_AI_Service SHALL trigger automatic summarization of older messages
2. WHEN the MemorySummarizer creates a summary THEN the Maritime_AI_Service SHALL preserve user emotional state (mệt, đói, vui) in the summary
3. WHEN retrieving context for a new message THEN the Maritime_AI_Service SHALL combine summaries with recent raw messages
4. WHEN the user asks "Nãy tôi than gì?" THEN the Maritime_AI_Service SHALL retrieve the relevant emotional context from summaries
5. WHEN MemorySummarizer is called from ChatService THEN the Maritime_AI_Service SHALL use the correct async method signature

### Requirement 2: User Name Persistence

**User Story:** As a user, I want the bot to remember my name across the conversation, so that interactions feel personal.

#### Acceptance Criteria

1. WHEN a user introduces themselves with patterns like "tên là X", "mình tên X" THEN the Maritime_AI_Service SHALL extract and store the name
2. WHEN a user name is stored THEN the Maritime_AI_Service SHALL persist it in both ChatHistory and SemanticMemory
3. WHEN generating a response THEN the Maritime_AI_Service SHALL use the stored name with 20-30% frequency (not every message)
4. WHEN the user returns in a new session THEN the Maritime_AI_Service SHALL retrieve their name from SemanticMemory

### Requirement 3: Anti-Repetition in Responses

**User Story:** As a user, I want varied responses from the bot, so that conversations don't feel robotic.

#### Acceptance Criteria

1. WHEN this is a follow-up message (not first in session) THEN the Maritime_AI_Service SHALL NOT start with greeting phrases like "Chào bạn"
2. WHEN generating multiple responses in a session THEN the Maritime_AI_Service SHALL vary opening phrases using the VariationPool
3. WHEN the same opening phrase was used in the last 3 responses THEN the Maritime_AI_Service SHALL select a different phrase
4. WHEN user expresses frustration or tiredness THEN the Maritime_AI_Service SHALL respond with empathy before providing information

### Requirement 4: Semantic Memory Retrieval

**User Story:** As a returning user, I want the bot to remember facts about me from previous sessions, so that I feel recognized.

#### Acceptance Criteria

1. WHEN a user starts a new session THEN the Maritime_AI_Service SHALL retrieve their stored facts from SemanticMemory
2. WHEN retrieving user facts THEN the Maritime_AI_Service SHALL prioritize recent and high-importance facts
3. WHEN user facts are available THEN the Maritime_AI_Service SHALL include them in the system prompt context
4. WHEN storing new facts THEN the Maritime_AI_Service SHALL categorize them by type (name, school, weakness, goal)

### Requirement 5: Conversation Context Continuity

**User Story:** As a user, I want the bot to maintain context throughout our conversation, so that follow-up questions work naturally.

#### Acceptance Criteria

1. WHEN a user asks a follow-up question like "Thế còn tàu cá thì sao?" THEN the Maritime_AI_Service SHALL understand the context from previous messages
2. WHEN building the prompt THEN the Maritime_AI_Service SHALL include formatted conversation history
3. WHEN conversation history exceeds token limit THEN the Maritime_AI_Service SHALL use summarized context instead of truncating
4. WHEN the user references something discussed earlier THEN the Maritime_AI_Service SHALL retrieve relevant context from TieredMemory

### Requirement 6: Pronoun Adaptation

**User Story:** As a user, I want the bot to adapt its pronouns based on how I communicate, so that conversations feel natural and personalized.

#### Acceptance Criteria

1. WHEN a user uses informal pronouns like "mình/cậu", "tớ/cậu", "anh/em", "chị/em" THEN the Maritime_AI_Service SHALL detect and store the preferred pronoun style
2. WHEN a pronoun style is detected THEN the Maritime_AI_Service SHALL adapt its responses to use matching pronouns instead of default "tôi/bạn"
3. WHEN the user changes pronoun style mid-conversation THEN the Maritime_AI_Service SHALL update and adapt to the new style
4. WHEN the detected pronouns contain inappropriate or vulgar terms THEN the Maritime_AI_Service SHALL ignore them and maintain default "tôi/bạn"
5. WHEN no specific pronoun style is detected THEN the Maritime_AI_Service SHALL use default "tôi/bạn" pronouns
