# Requirements Document

## Introduction

Tài liệu này mô tả yêu cầu cho việc tái cấu trúc dự án maritime-ai-service, bao gồm: tổ chức lại thư mục tests/scripts, loại bỏ mã legacy, refactor semantic memory, và hợp nhất tài liệu. Mục tiêu là chuẩn hóa cấu trúc dự án, loại bỏ mã chết, và chuẩn bị cho khả năng mở rộng.

## Glossary

- **Maritime_AI_Service**: Hệ thống AI hỗ trợ học tập và tra cứu kiến thức hàng hải
- **UnifiedAgent**: Agent chính hiện tại xử lý tất cả các tương tác chat
- **ChatAgent**: Agent legacy đã được thay thế bởi UnifiedAgent
- **SemanticMemoryEngine**: Engine quản lý bộ nhớ ngữ nghĩa của hệ thống
- **E2E Tests**: Các bài test end-to-end kiểm tra toàn bộ luồng hệ thống
- **Integration Tests**: Các bài test kiểm tra tích hợp giữa các module
- **Unit Tests**: Các bài test kiểm tra từng đơn vị code riêng lẻ
- **Property Tests**: Các bài test dựa trên thuộc tính (property-based testing)

## Requirements

### Requirement 1: Scripts/Tests Reorganization (P0)

**User Story:** As a developer, I want test files organized by category (e2e, integration, unit), so that I can easily find and run specific test types.

#### Acceptance Criteria

1. WHEN pytest discovers tests in the tests/ directory THEN the Maritime_AI_Service SHALL return all test files organized in e2e/, integration/, unit/, and property/ subdirectories
2. WHEN a test file with "_e2e" or "_production" suffix exists in scripts/ THEN the Maritime_AI_Service SHALL move that file to tests/e2e/
3. WHEN a test file with "_integration" suffix or guardian/search integration tests exist in scripts/ THEN the Maritime_AI_Service SHALL move that file to tests/integration/
4. WHEN remaining test files exist in scripts/ THEN the Maritime_AI_Service SHALL move those files to tests/unit/
5. WHEN SQL migration files exist in scripts/ THEN the Maritime_AI_Service SHALL organize them into scripts/migrations/
6. WHEN data import scripts exist in scripts/ THEN the Maritime_AI_Service SHALL organize them into scripts/data/
7. WHEN utility scripts (check_*, verify_*) exist in scripts/ THEN the Maritime_AI_Service SHALL organize them into scripts/utils/

### Requirement 2: Legacy Code Analysis and Handling (P1)

**User Story:** As a developer, I want legacy code analyzed and handled appropriately, so that the codebase is clean while maintaining system stability.

#### Acceptance Criteria

1. WHEN analyzing legacy code THEN the Maritime_AI_Service SHALL identify all fallback paths using ChatAgent and AgentOrchestrator in chat_service.py
2. WHEN legacy code is used as fallback THEN the Maritime_AI_Service SHALL document the conditions under which fallback is triggered
3. IF legacy code is confirmed unused in production THEN the Maritime_AI_Service SHALL archive app/engine/agents/chat_agent.py and app/engine/graph.py to archive/ folder
4. IF legacy code is still needed as fallback THEN the Maritime_AI_Service SHALL keep the code but add deprecation warnings
5. WHEN any changes to legacy code are made THEN the Maritime_AI_Service SHALL verify the application still functions correctly with both UnifiedAgent and fallback paths

### Requirement 3: Semantic Memory Refactoring (P2)

**User Story:** As a developer, I want semantic_memory.py split into smaller modules, so that the code is more maintainable and testable.

#### Acceptance Criteria

1. WHEN semantic_memory.py exceeds 500 lines THEN the Maritime_AI_Service SHALL split it into separate modules (core.py, context.py, extraction.py)
2. WHEN the refactoring is complete THEN the Maritime_AI_Service SHALL provide a facade class (SemanticMemoryEngine) in __init__.py that maintains backward compatibility
3. WHEN importing SemanticMemoryEngine THEN the Maritime_AI_Service SHALL allow imports from both app.engine.semantic_memory and app.engine.semantic_memory.core
4. WHEN all semantic memory tests run THEN the Maritime_AI_Service SHALL pass with the refactored module structure

### Requirement 4: Documentation Consolidation (P3)

**User Story:** As a developer, I want semantic memory documentation consolidated into a single file, so that I can understand the current architecture without reading multiple version files.

#### Acceptance Criteria

1. WHEN multiple SEMANTIC_MEMORY_V*.md files exist THEN the Maritime_AI_Service SHALL merge them into a single SEMANTIC_MEMORY_ARCHITECTURE.md
2. WHEN creating the consolidated document THEN the Maritime_AI_Service SHALL include a Version History section documenting changes across versions
3. WHEN the consolidation is complete THEN the Maritime_AI_Service SHALL archive or delete the individual version files

### Requirement 5: Verification and Testing

**User Story:** As a developer, I want automated verification that the restructuring is successful, so that I can be confident the system still works correctly.

#### Acceptance Criteria

1. WHEN running pytest tests/ --collect-only THEN the Maritime_AI_Service SHALL discover all moved test files
2. WHEN running the full test suite THEN the Maritime_AI_Service SHALL pass all existing tests
3. WHEN starting the server with uvicorn THEN the Maritime_AI_Service SHALL respond to /chat endpoint correctly
4. WHEN testing Guardian Agent THEN the Maritime_AI_Service SHALL function correctly after restructuring
5. WHEN testing RAG search THEN the Maritime_AI_Service SHALL return relevant results after restructuring
