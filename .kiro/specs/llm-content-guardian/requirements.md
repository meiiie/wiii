# Requirements Document

## Introduction

Spec này tập trung vào việc sử dụng LLM (Gemini) như một "Guardian Agent" để xử lý content moderation thông minh hơn, thay vì dựa vào hardcoded patterns. Mục tiêu là:

1. Phát hiện từ tục tĩu/nhạy cảm một cách linh hoạt (không cần maintain danh sách dài)
2. Xử lý các yêu cầu xưng hô đặc biệt từ user (ví dụ: "gọi tôi là công chúa và bạn là trẫm")
3. Phân biệt được context để không block nhầm (ví dụ: "tàu cướp biển" trong ngữ cảnh hàng hải)

**Phạm vi:** Nâng cấp Guardrails hiện có với LLM-based validation

**Tham chiếu:** CHỈ THỊ KỸ THUẬT SỐ 21 - LLM Content Guardian

## Glossary

- **Maritime_AI_Service**: Hệ thống AI Tutor hỗ trợ học viên hàng hải
- **Guardian_Agent**: LLM-based agent chuyên xử lý content moderation
- **Pronoun_Request**: Yêu cầu từ user về cách xưng hô đặc biệt (custom pronouns)
- **Content_Moderation**: Quá trình kiểm tra và lọc nội dung không phù hợp
- **Guardrails**: Module hiện tại xử lý input/output validation (rule-based)
- **Contextual_Analysis**: Phân tích ngữ cảnh để hiểu ý nghĩa thực sự của nội dung

## Requirements

### Requirement 1: LLM-based Pronoun Request Validation

**User Story:** As a user, I want to request custom pronouns/nicknames, so that the AI can address me in a personalized way.

#### Acceptance Criteria

1. WHEN a user requests a custom pronoun like "gọi tôi là công chúa" THEN the Guardian_Agent SHALL analyze the request using LLM
2. WHEN the custom pronoun request is appropriate THEN the Guardian_Agent SHALL approve and return the pronoun pair (user_called, ai_self)
3. WHEN the custom pronoun request contains inappropriate content THEN the Guardian_Agent SHALL reject and return default pronouns
4. WHEN analyzing pronoun requests THEN the Guardian_Agent SHALL consider Vietnamese cultural context and roleplay scenarios

### Requirement 2: LLM-based Inappropriate Content Detection

**User Story:** As a system administrator, I want intelligent content filtering, so that inappropriate content is blocked without false positives.

#### Acceptance Criteria

1. WHEN a user message contains potentially inappropriate content THEN the Guardian_Agent SHALL analyze using LLM instead of keyword matching
2. WHEN the content is contextually appropriate (e.g., "cướp biển" in maritime context) THEN the Guardian_Agent SHALL allow it
3. WHEN the content is genuinely inappropriate (tục tĩu, xúc phạm) THEN the Guardian_Agent SHALL block and log the reason
4. WHEN uncertain about content appropriateness THEN the Guardian_Agent SHALL flag for review rather than block

### Requirement 3: Fallback to Rule-based Filtering

**User Story:** As a system, I want fallback mechanisms, so that content moderation works even when LLM is unavailable.

#### Acceptance Criteria

1. WHEN the LLM Guardian is unavailable THEN the Maritime_AI_Service SHALL fallback to rule-based filtering (current Guardrails)
2. WHEN LLM response is slow (>2 seconds) THEN the Maritime_AI_Service SHALL use rule-based filtering
3. WHEN fallback is used THEN the Maritime_AI_Service SHALL log the event for monitoring

### Requirement 4: Custom Pronoun Storage and Retrieval

**User Story:** As a user, I want my custom pronoun preferences remembered, so that I don't have to repeat them.

#### Acceptance Criteria

1. WHEN a custom pronoun is approved THEN the Maritime_AI_Service SHALL store it in SessionState
2. WHEN generating responses THEN the Maritime_AI_Service SHALL use the stored custom pronoun
3. WHEN the user requests to change their pronoun THEN the Maritime_AI_Service SHALL update the preference immediately
4. WHEN the custom pronoun is inappropriate THEN the Maritime_AI_Service SHALL NOT store it and use default

### Requirement 5: Performance and Cost Optimization

**User Story:** As a system operator, I want efficient LLM usage, so that costs are controlled and latency is acceptable.

#### Acceptance Criteria

1. WHEN validating content THEN the Guardian_Agent SHALL use a lightweight prompt (minimal tokens)
2. WHEN the same content pattern is seen repeatedly THEN the Guardian_Agent SHALL cache the decision
3. WHEN LLM validation is not needed (simple greetings) THEN the Guardian_Agent SHALL skip LLM call
4. WHEN processing requests THEN the Guardian_Agent SHALL complete validation within 500ms average

