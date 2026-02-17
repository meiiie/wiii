# Requirements Document: Deep Reasoning & Smart Context Engine (CHỈ THỊ 21)

## Introduction

Nâng cấp Maritime AI từ "Chatbot trả lời câu hỏi" thành "Chuyên gia tư duy" với khả năng:
- Internal Monologue (Độc thoại nội tâm) trong thẻ `<thinking>`
- Self-Correction (Tự phản biện)
- Context-aware reasoning (Kiểm tra ký ức, lập chiến lược)
- Hybrid Memory với Large Context Window (50+ messages)
- Proactive behavior (Chủ động hỏi user muốn nghe tiếp không)

Tham chiếu: #[[file:Documents/phanhoi/chithi21.md]]

## Glossary

- **Deep Reasoning**: Quá trình AI suy nghĩ trước khi trả lời, thể hiện qua thẻ `<thinking>`
- **Internal Monologue**: Độc thoại nội tâm - AI tự nói chuyện với chính mình để phân tích
- **Self-Correction**: Tự phản biện - AI nghi ngờ và kiểm tra lại suy luận của mình
- **Context Window**: Cửa sổ ngữ cảnh - số lượng messages được gửi cho LLM
- **Chain of Thought (CoT)**: Chuỗi suy luận - kỹ thuật giúp giảm hallucination
- **Proactive Behavior**: Hành vi chủ động - AI tự đề xuất tiếp tục giải thích dở
- **Hybrid Memory**: Bộ nhớ lai - kết hợp Vector DB (dài hạn) và Context Window (ngắn hạn)
- **System**: Maritime AI Backend Service

## Requirements

### Requirement 1: Deep Reasoning with Thinking Tags

**User Story:** As a student, I want the AI to think deeply before answering, so that I receive more accurate and well-reasoned responses.

#### Acceptance Criteria

1. WHEN the System processes a user message THEN the System SHALL generate a `<thinking>` section before the final response
2. WHEN generating the thinking section THEN the System SHALL include self-correction phrases (e.g., "Khoan đã, liệu hiểu thế này có đúng không?")
3. WHEN generating the thinking section THEN the System SHALL check user context from memory (e.g., "User này là ai? Mình vừa chào họ chưa?")
4. WHEN generating the thinking section THEN the System SHALL plan the response strategy (e.g., "Câu này cần trích dẫn Rule nào?")
5. THE response format SHALL follow pattern: `<thinking>[reasoning]</thinking>[final answer]`

### Requirement 2: Large Context Window

**User Story:** As a system architect, I want to use Gemini's large context window, so that the AI can understand pronouns and references across the conversation.

#### Acceptance Criteria

1. WHEN retrieving chat history THEN the System SHALL fetch up to 50 recent messages
2. WHEN building context THEN the System SHALL include all non-blocked messages in chronological order
3. WHEN the System encounters pronouns in user message THEN the System SHALL resolve them using conversation history
4. THE System SHALL NOT use complex compression algorithms for short-term memory within a session

### Requirement 3: Proactive Conversation Continuity

**User Story:** As a student, I want the AI to remember what we were discussing, so that it can offer to continue interrupted explanations.

#### Acceptance Criteria

1. WHEN the user asks a new question while a previous explanation was incomplete THEN the System SHALL note this in `<thinking>` section
2. WHEN the System answers a new question after an incomplete explanation THEN the System SHALL offer to continue the previous topic
3. WHEN offering to continue THEN the System SHALL phrase it naturally (e.g., "Nãy mình đang nói dở về Rule 15, bạn muốn nghe tiếp không?")
4. WHEN analyzing conversation THEN the System SHALL track incomplete topics in the thinking process
5. WHEN detecting incomplete explanation THEN the System SHALL identify the specific topic that was interrupted

### Requirement 4: Response Format Consistency

**User Story:** As a frontend developer, I want consistent response format, so that I can parse and display the thinking section correctly.

#### Acceptance Criteria

1. WHEN deep reasoning is enabled THEN the response SHALL always contain `<thinking>` tags
2. THE `<thinking>` section SHALL appear BEFORE the final answer in the response
3. THE final answer SHALL appear AFTER the closing `</thinking>` tag
4. IF deep reasoning is disabled THEN the System SHALL return only the final answer without tags
5. THE System SHALL ensure `<thinking>` tags are properly closed and well-formed

### Requirement 5: Hybrid Memory Integration

**User Story:** As a system architect, I want to combine Vector DB (long-term) with Large Context Window (short-term), so that the AI has comprehensive memory.

#### Acceptance Criteria

1. WHEN starting a request THEN the System SHALL query Vector DB for user facts (name, level, weak topics)
2. WHEN building the prompt THEN the System SHALL inject user facts into the system prompt
3. WHEN building the prompt THEN the System SHALL include recent 50 messages as conversation history
4. WHEN facts conflict between Vector DB and conversation THEN the System SHALL prioritize Vector DB facts for consistency
5. THE System SHALL NOT save blocked messages to Vector DB (per CHỈ THỊ 22 - Memory Isolation)

### Requirement 6: Thinking Tag Parsing and Display

**User Story:** As a frontend developer, I want to parse and optionally display the thinking section, so that users can see how the AI reasons.

#### Acceptance Criteria

1. WHEN the frontend receives a response with `<thinking>` tags THEN the frontend SHALL parse and extract the thinking content
2. WHEN displaying in Clean Mode THEN the frontend SHALL hide the `<thinking>` section and show only the final answer
3. WHEN displaying in Debug Mode THEN the frontend SHALL show the `<thinking>` section in a collapsible panel
4. THE frontend SHALL provide a toggle button (💡 or 🧠 icon) to switch between Clean and Debug modes
5. WHEN parsing fails THEN the frontend SHALL display the raw response without crashing
