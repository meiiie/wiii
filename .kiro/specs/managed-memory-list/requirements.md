# Requirements Document

## Introduction

Tối ưu hóa module Semantic Memory theo chuẩn Industry (Qwen/OpenAI) với Managed Memory List. Hệ thống hiện tại đã có Atomic Facts và Semantic Search, nhưng thiếu Memory Capping và True Deduplication. Feature này sẽ implement Memory Capping (50 facts/user), True Deduplication (Upsert), và Memory Management API.

## Glossary

- **Semantic Memory**: Module lưu trữ thông tin người dùng dưới dạng vector embeddings
- **User Fact**: Thông tin cô đọng về người dùng (tên, mục tiêu, sở thích...)
- **Memory Capping**: Giới hạn số lượng facts tối đa cho mỗi user
- **FIFO (First In First Out)**: Cơ chế xóa facts cũ nhất khi vượt quá giới hạn
- **Upsert**: Update nếu tồn tại, Insert nếu chưa có
- **Eviction Policy**: Chính sách loại bỏ dữ liệu cũ khi đầy
- **fact_type**: Loại thông tin (name, role, level, goal, preference, weakness)

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want to limit the number of facts stored per user, so that the database does not grow unbounded and AI context remains clean.

#### Acceptance Criteria

1. WHEN a new fact is stored for a user THEN the Semantic Memory System SHALL check if the user has reached the maximum limit of 50 facts
2. WHEN the user has reached 50 facts and a new fact is added THEN the Semantic Memory System SHALL delete the oldest fact (FIFO) before storing the new one
3. WHEN counting user facts THEN the Semantic Memory System SHALL only count facts of type USER_FACT, excluding MESSAGE and SUMMARY types
4. WHEN the memory cap is enforced THEN the Semantic Memory System SHALL log the deletion of old facts for audit purposes

### Requirement 2

**User Story:** As a user, I want my updated information to replace old information, so that the AI always has my most current details.

#### Acceptance Criteria

1. WHEN a user provides new information of the same fact_type THEN the Semantic Memory System SHALL update the existing fact instead of creating a duplicate
2. WHEN updating a fact THEN the Semantic Memory System SHALL preserve the original fact ID and update the content, embedding, and timestamp
3. WHEN no existing fact of the same type exists THEN the Semantic Memory System SHALL create a new fact entry
4. WHEN a fact is updated THEN the Semantic Memory System SHALL update the `updated_at` timestamp to reflect the change

### Requirement 3

**User Story:** As a developer, I want to retrieve a user's stored facts via API, so that I can build a memory management UI in the future.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/v1/memories/{user_id}` THEN the API SHALL return a JSON array of all facts for that user
2. WHEN returning facts THEN the API SHALL include id, type, value, and created_at fields for each fact
3. WHEN the user has no facts THEN the API SHALL return an empty array with status 200
4. WHEN an unauthorized request is made THEN the API SHALL return status 401 with appropriate error message

### Requirement 4

**User Story:** As a system architect, I want to limit fact_types to essential categories, so that the memory system remains focused and efficient.

#### Acceptance Criteria

1. WHEN extracting facts from user messages THEN the Semantic Memory System SHALL only extract facts of allowed types: name, role, level, goal, preference, weakness
2. WHEN an LLM attempts to extract a fact with an unsupported type THEN the Semantic Memory System SHALL ignore that fact
3. WHEN validating fact_type THEN the Semantic Memory System SHALL use case-insensitive comparison
