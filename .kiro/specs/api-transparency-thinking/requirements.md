# Requirements Document

## Introduction

Cải tiến API response để tăng tính minh bạch (transparency) và đảm bảo AI luôn suy luận (thinking) trước khi trả lời câu hỏi kiến thức hàng hải. Hai vấn đề cần giải quyết:

1. **Tools Used**: API hiện không trả về `tools_used` - LMS/frontend không biết AI đã dùng tool gì
2. **Thinking Tag**: AI không nhất quán dùng `<thinking>` cho RAG queries - cần bắt buộc để đảm bảo suy luận

## Glossary

- **tools_used**: Danh sách các tool mà AI đã gọi trong quá trình xử lý (tool_maritime_search, tool_save_user_info, tool_get_user_info)
- **thinking tag**: Tag `<thinking>...</thinking>` chứa quá trình suy luận của AI trước khi đưa ra câu trả lời
- **RAG query**: Câu hỏi về kiến thức hàng hải cần tra cứu từ Knowledge Graph
- **ChatResponseMetadata**: Schema metadata trong API response
- **UnifiedAgent**: Agent chính xử lý message với ReAct pattern

## Requirements

### Requirement 1: Expose Tools Used in API Response

**User Story:** As a LMS developer, I want to see which tools the AI used to process my request, so that I can debug issues and understand AI behavior.

#### Acceptance Criteria

1. WHEN the UnifiedAgent processes a message THEN the ChatResponseMetadata SHALL include a `tools_used` field containing the list of tools called
2. WHEN no tools are called THEN the `tools_used` field SHALL be an empty list
3. WHEN tools are called THEN each entry in `tools_used` SHALL contain the tool name and a brief description of what it did
4. WHEN the API response is serialized THEN the `tools_used` field SHALL be properly formatted as JSON array

### Requirement 2: Mandatory Thinking for RAG Queries

**User Story:** As a maritime student, I want the AI to always show its reasoning process when answering knowledge questions, so that I can learn how to think about maritime regulations.

#### Acceptance Criteria

1. WHEN the AI calls `tool_maritime_search` THEN the response SHALL include a `<thinking>` tag with reasoning about the query
2. WHEN the AI receives RAG results THEN the `<thinking>` tag SHALL explain how the AI interprets and synthesizes the information
3. WHEN the AI answers without calling tools (empathy, greeting) THEN the `<thinking>` tag SHALL be optional
4. WHEN the SYSTEM_PROMPT is built THEN it SHALL include explicit instructions requiring `<thinking>` for knowledge queries

### Requirement 3: Backward Compatibility

**User Story:** As a LMS developer, I want the API changes to be backward compatible, so that existing integrations continue to work.

#### Acceptance Criteria

1. WHEN the API response format changes THEN existing fields (answer, sources, suggested_questions) SHALL remain unchanged
2. WHEN `tools_used` is added THEN it SHALL be an optional field with default empty list
3. WHEN frontend does not handle `<thinking>` tag THEN the response SHALL still be valid and usable
