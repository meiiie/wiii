# Requirements Document

## Introduction

Cải thiện chất lượng phản hồi của AI Chatbot trong hệ thống Maritime AI Tutor. Hiện tại, team LMS phản hồi rằng AI trả lời chưa tốt - máy móc, thiếu cá nhân hóa, không tận dụng được Tutor Agent có sẵn. Spec này tập trung vào việc nâng cao trải nghiệm người dùng thông qua cải thiện persona, response style, và tích hợp các tính năng giảng dạy.

## Glossary

- **Unified Agent**: Agent chính sử dụng ReAct pattern với LangChain, điều phối các tools để trả lời user
- **Persona**: Nhân cách của AI, được cấu hình qua YAML files (tutor.yaml, assistant.yaml)
- **Response Quality**: Chất lượng phản hồi bao gồm độ tự nhiên, cá nhân hóa, độ chính xác, và độ phù hợp ngữ cảnh
- **Empathy First**: Nguyên tắc đồng cảm trước khi trả lời - khi user than vãn, AI chia sẻ cảm xúc trước
- **Tutor Agent**: Agent chuyên về giảng dạy với các phases: Introduction → Explanation → Assessment
- **Semantic Memory**: Bộ nhớ ngữ nghĩa lưu trữ user facts và conversation context qua các sessions
- **Tool**: Function mà LLM có thể gọi trong ReAct loop (VD: tool_maritime_search, tool_save_user_info)
- **Few-shot Examples**: Các ví dụ mẫu trong prompt để hướng dẫn AI cách trả lời

## Requirements

### Requirement 1: Cải thiện Persona và Giọng văn

**User Story:** As a student, I want the AI to respond naturally like a friendly mentor, so that I feel comfortable learning and asking questions.

#### Acceptance Criteria

1. WHEN a student sends a message THEN the System SHALL respond with a warm, friendly tone as defined in tutor.yaml persona configuration
2. WHEN a student expresses frustration or tiredness (e.g., "mệt quá", "chán học") THEN the System SHALL apply Empathy First principle by acknowledging their feelings before providing any educational content
3. WHEN the System has the user's name stored in memory THEN the System SHALL use the name naturally (20-30% of responses) without repetitive greeting patterns
4. WHEN responding to follow-up questions THEN the System SHALL NOT repeat greetings or the user's name at the start of every response
5. WHEN a teacher or admin sends a message THEN the System SHALL respond with professional, respectful tone using appropriate honorifics (Thầy/Cô, Anh/Chị) as defined in assistant.yaml

### Requirement 2: Tối ưu Response Length và Format

**User Story:** As a user, I want AI responses to be appropriately sized based on my question complexity, so that I get concise answers for simple questions and detailed explanations when needed.

#### Acceptance Criteria

1. WHEN a user asks a simple question (less than 10 words, single concept) THEN the System SHALL provide a concise response (50-150 words)
2. WHEN a user asks a complex question (multiple concepts, "giải thích chi tiết") THEN the System SHALL provide a comprehensive response (200-400 words) with structured formatting
3. WHEN providing maritime knowledge THEN the System SHALL include relevant citations and source references
4. WHEN explaining technical terms THEN the System SHALL provide Vietnamese translations for English maritime terms (starboard = mạn phải, port = mạn trái)
5. WHEN the response contains multiple points THEN the System SHALL use appropriate formatting (bold keywords, numbered lists for steps)

### Requirement 3: Tích hợp Tutor Agent vào Unified Agent

**User Story:** As a student, I want to be able to request quizzes and assessments through the chat, so that I can test my knowledge interactively.

#### Acceptance Criteria

1. WHEN a user requests a quiz or test (e.g., "kiểm tra kiến thức", "quiz về COLREGs") THEN the System SHALL invoke the Tutor Agent to start an assessment session
2. WHEN a teaching session is active THEN the System SHALL guide the user through Introduction → Explanation → Assessment phases
3. WHEN a user answers a quiz question THEN the System SHALL evaluate the answer and provide feedback with hints for incorrect answers
4. WHEN a user achieves mastery (≥80% score with ≥3 questions) THEN the System SHALL congratulate and record the achievement
5. WHEN a user is struggling (less than 50% score after 3 questions) THEN the System SHALL offer additional explanations and suggest reviewing the topic

### Requirement 4: Cải thiện Memory Utilization

**User Story:** As a returning user, I want the AI to remember my previous conversations and preferences, so that I don't have to repeat information.

#### Acceptance Criteria

1. WHEN a user returns to chat THEN the System SHALL retrieve and utilize stored user facts (name, role, learning goals) from Semantic Memory
2. WHEN a user mentions personal information (name, school, profession) THEN the System SHALL extract and store these facts for future sessions
3. WHEN conversation history exceeds the token threshold THEN the System SHALL summarize older messages while preserving key context
4. WHEN retrieving context THEN the System SHALL prioritize recent interactions and high-importance facts
5. WHEN a user asks about previous conversations (e.g., "nãy tôi hỏi gì") THEN the System SHALL reference the conversation summary accurately

### Requirement 5: Thêm Tools mới cho Unified Agent

**User Story:** As a student, I want the AI to have more capabilities beyond just searching knowledge, so that I can get help with learning activities.

#### Acceptance Criteria

1. WHEN a user requests a quiz THEN the System SHALL have access to a tool_start_quiz tool that initiates Tutor Agent sessions
2. WHEN a user asks for topic suggestions THEN the System SHALL have access to a tool_suggest_topics tool that recommends learning paths based on user's history
3. WHEN a user asks to compare regulations THEN the System SHALL have access to a tool_compare_rules tool that presents side-by-side comparisons
4. WHEN a user asks for term explanation THEN the System SHALL have access to a tool_explain_term tool that provides detailed terminology breakdowns with examples
5. WHEN tools are called THEN the System SHALL log tool usage for analytics and debugging purposes

### Requirement 6: Cải thiện Tool Descriptions

**User Story:** As a system architect, I want the LLM to make better decisions about when to call tools, so that responses are more accurate and relevant.

#### Acceptance Criteria

1. WHEN defining tool_maritime_search THEN the System SHALL include detailed description with explicit WHEN TO CALL and WHEN NOT TO CALL guidelines
2. WHEN defining tool_save_user_info THEN the System SHALL specify exact patterns that trigger fact extraction (name introduction, profession mention)
3. WHEN the LLM decides to call a tool THEN the decision SHALL be based on clear keyword matching and intent recognition from the tool description
4. WHEN a greeting or casual conversation is detected THEN the System SHALL NOT call knowledge search tools unnecessarily
5. WHEN multiple tools could apply THEN the System SHALL have priority rules defined in tool descriptions

### Requirement 7: Response Variation và Anti-Repetition

**User Story:** As a user, I want the AI to vary its responses and not repeat the same patterns, so that conversations feel natural and engaging.

#### Acceptance Criteria

1. WHEN generating responses THEN the System SHALL vary opening phrases and NOT start every response with the same pattern
2. WHEN the user's name is known THEN the System SHALL NOT include the name in every response, limiting to contextually appropriate moments
3. WHEN responding to similar questions THEN the System SHALL use different phrasings and examples
4. WHEN the System detects it has used a phrase recently THEN the System SHALL select an alternative from the variation pool
5. WHEN providing examples THEN the System SHALL draw from a diverse set of maritime scenarios (different ship types, situations, regulations)

### Requirement 8: Suggested Questions Generation

**User Story:** As a student, I want the AI to suggest follow-up questions after each response, so that I can continue learning effectively.

#### Acceptance Criteria

1. WHEN the System provides a knowledge-based response THEN the System SHALL generate 2-3 contextually relevant follow-up questions
2. WHEN generating suggestions THEN the System SHALL base them on the current topic and user's learning history
3. WHEN the user has weak areas recorded THEN the System SHALL occasionally suggest questions that address those gaps
4. WHEN suggestions are generated THEN the System SHALL ensure they are progressively more advanced to encourage deeper learning
5. WHEN the API returns a response THEN the suggested_questions field SHALL contain the generated suggestions

