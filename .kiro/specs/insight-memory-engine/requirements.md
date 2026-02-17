# Requirements Document

## Introduction

Nâng cấp Semantic Memory từ lưu trữ "Atomic Facts" (dữ liệu đơn lẻ) sang "Behavioral Insights" (sự thấu hiểu hành vi). Mục tiêu là biến AI từ "Thư ký" thành "Người Thầy (Mentor)" thực thụ - có khả năng hiểu sâu về phong cách học tập, lỗ hổng kiến thức, và sự thay đổi của người dùng.

**Spec Reference:** CHỈ THỊ KỸ THUẬT SỐ 23 - CẢI TIẾN (Insight Engine)
**Previous Version:** Semantic Memory v0.4 (Managed Memory List)

## Glossary

- **Insight**: Sự thấu hiểu sâu về hành vi, phong cách, hoặc xu hướng của người dùng (không chỉ là fact đơn lẻ)
- **Atomic Fact**: Dữ liệu đơn giản như tên, tuổi, nghề nghiệp
- **Behavioral Insight**: Câu văn hoàn chỉnh mô tả ngữ cảnh và sở thích phức tạp
- **Memory Consolidation**: Quy trình gộp và tinh gọn các memories trùng lặp
- **Insight Engine**: Module trích xuất insights từ conversation
- **FIFO**: First In First Out - cơ chế xóa memory cũ nhất khi đầy

## Requirements

### Requirement 1: Insight Extraction Prompt

**User Story:** As an AI system, I want to extract behavioral insights from conversations, so that I can understand users deeply beyond simple facts.

#### Acceptance Criteria

1. WHEN the system extracts information from a user message THEN the Insight_Engine SHALL identify learning style patterns (lý thuyết vs thực hành, tư duy phản biện)
2. WHEN the system detects a knowledge gap THEN the Insight_Engine SHALL record the specific misconception or confusion area
3. WHEN the system detects a goal change THEN the Insight_Engine SHALL record the evolution (e.g., "User đã chuyển từ học cơ bản sang ôn thi thuyền trưởng")
4. WHEN the system extracts an insight THEN the Insight_Engine SHALL format it as a complete sentence describing context and preference
5. WHEN the extraction prompt is invoked THEN the Insight_Engine SHALL prioritize behavioral patterns over atomic facts

### Requirement 2: Memory Consolidation

**User Story:** As an AI system, I want to consolidate memories when approaching capacity, so that I maintain high-quality insights without redundancy.

#### Acceptance Criteria

1. WHEN the memory count reaches 40 out of 50 THEN the Insight_Engine SHALL trigger the consolidation process
2. WHEN consolidation is triggered THEN the Insight_Engine SHALL call LLM to rewrite and merge duplicate insights
3. WHEN consolidation completes THEN the Insight_Engine SHALL reduce memory count to maximum 30 core items
4. WHEN insights are merged THEN the Insight_Engine SHALL preserve the most recent and relevant information
5. WHEN consolidation fails THEN the Insight_Engine SHALL log the error and continue with FIFO eviction

### Requirement 3: Hard Limit Enforcement

**User Story:** As an AI system, I want to enforce a hard limit of 50 memories per user, so that the system remains performant and focused.

#### Acceptance Criteria

1. WHEN memory count exceeds 50 THEN the Insight_Engine SHALL prevent new insertions until consolidation runs
2. WHEN consolidation cannot reduce below 50 THEN the Insight_Engine SHALL delete memories with oldest last_accessed timestamp
3. WHEN a memory is accessed THEN the Insight_Engine SHALL update its last_accessed timestamp
4. WHEN deleting by last_accessed THEN the Insight_Engine SHALL preserve memories accessed within the last 7 days

### Requirement 4: Insight Categories

**User Story:** As an AI system, I want to categorize insights by type, so that I can retrieve relevant context efficiently.

#### Acceptance Criteria

1. WHEN extracting insights THEN the Insight_Engine SHALL categorize into: learning_style, knowledge_gap, goal_evolution, habit, preference
2. WHEN storing an insight THEN the Insight_Engine SHALL include the category in metadata
3. WHEN retrieving context THEN the Insight_Engine SHALL prioritize knowledge_gap and learning_style categories
4. WHEN a category has multiple insights THEN the Insight_Engine SHALL keep only the most recent per sub-topic

### Requirement 5: Insight Quality Validation

**User Story:** As an AI system, I want to validate insight quality before storage, so that only meaningful insights are persisted.

#### Acceptance Criteria

1. WHEN an insight is extracted THEN the Insight_Engine SHALL verify it contains behavioral or contextual information
2. WHEN an insight is too short (less than 20 characters) THEN the Insight_Engine SHALL reject it as atomic fact
3. WHEN an insight duplicates existing content THEN the Insight_Engine SHALL merge instead of append
4. WHEN an insight contradicts existing insight THEN the Insight_Engine SHALL update the existing one with evolution note
