# Implementation Plan

## Overview
Implementation plan cho Admin Tool Management API - cho phép Admin giám sát và quản lý AI Tools trong Maritime AI Tutor.

---

- [ ] 1. Database Schema và Models
  - [ ] 1.1 Tạo SQL migration script cho tool_call_logs và admin_audit_logs tables
    - Tạo file `scripts/create_tool_management_tables.sql`
    - Bao gồm indexes cho performance
    - _Requirements: 6.1, 3.3, 7.3_
  - [ ] 1.2 Tạo Pydantic models cho Tool Management
    - Tạo file `app/models/tool_management.py`
    - Định nghĩa ToolInfo, ToolStats, ToolCallLog, ToolConfig models
    - Định nghĩa request/response schemas
    - _Requirements: 1.1, 2.1, 5.1, 6.1_
  - [ ]* 1.3 Write property test cho model serialization round-trip
    - **Property: Serialization round trip**
    - *For any* valid ToolInfo/ToolStats object, serializing to JSON then deserializing SHALL produce equivalent object
    - **Validates: Requirements 1.1, 2.1**

- [ ] 2. Tool Registry Service
  - [ ] 2.1 Implement ToolRegistry singleton class
    - Tạo file `app/services/tool_registry.py`
    - Implement register_tool, get_all_tools, get_tool methods
    - Implement enable_tool, disable_tool với critical tool check
    - Implement update_config với validation
    - _Requirements: 1.1, 2.1, 3.1, 3.2, 4.1_
  - [ ]* 2.2 Write property test: Tool List Completeness
    - **Property 1: Tool List Completeness**
    - *For any* registered tools, get_all_tools() SHALL return all tools with required fields
    - **Validates: Requirements 1.1, 1.2**
  - [ ]* 2.3 Write property test: Enable-Disable Round Trip
    - **Property 5: Enable-Disable Round Trip**
    - *For any* tool, disable then enable SHALL restore callable state
    - **Validates: Requirements 3.2**
  - [ ]* 2.4 Write property test: Config Validation
    - **Property 7: Config Validation**
    - *For any* invalid config values, update_config SHALL reject with errors
    - **Validates: Requirements 4.1, 4.2**

- [ ] 3. Tool Stats và Logging Repository
  - [ ] 3.1 Implement ToolCallRepository cho logging
    - Tạo file `app/repositories/tool_call_repository.py`
    - Implement record_call, get_logs với filtering và pagination
    - Implement get_stats với time range support
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3_
  - [ ]* 3.2 Write property test: Log Pagination
    - **Property 10: Log Pagination**
    - *For any* limit L và offset O, response SHALL return at most L entries from position O
    - **Validates: Requirements 6.3**
  - [ ]* 3.3 Write property test: Stats Completeness
    - **Property 9: Stats Completeness**
    - *For any* stats request, response SHALL include call counts, success rate, avg latency
    - **Validates: Requirements 5.1, 5.3**

- [ ] 4. Audit Log Repository
  - [ ] 4.1 Implement AuditLogRepository
    - Tạo file `app/repositories/audit_log_repository.py`
    - Implement log_action method
    - _Requirements: 3.3, 4.4, 7.3_
  - [ ]* 4.2 Write property test: Action Logging
    - **Property 6: Action Logging**
    - *For any* admin action, audit log entry SHALL be created with admin_id, timestamp, details
    - **Validates: Requirements 3.3, 4.4**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Admin API Endpoints
  - [ ] 6.1 Implement GET /api/v1/admin/tools endpoint
    - Tạo file `app/api/v1/admin/tools.py`
    - Return list of all tools với status và config
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ] 6.2 Implement GET /api/v1/admin/tools/{name} endpoint
    - Return tool details với dependencies status
    - Return 404 nếu tool không tồn tại
    - _Requirements: 2.1, 2.2, 2.3_
  - [ ]* 6.3 Write property test: Non-existent Tool Returns 404
    - **Property 3: Non-existent Tool Returns 404**
    - *For any* non-registered tool name, GET SHALL return HTTP 404
    - **Validates: Requirements 2.2**
  - [ ] 6.4 Implement PUT /api/v1/admin/tools/{name} endpoint
    - Support enable/disable và config update
    - Validate config against schema
    - Require confirmation cho critical tools
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4_
  - [ ] 6.5 Implement GET /api/v1/admin/tools/stats endpoint
    - Return usage statistics với time range filter
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 6.6 Implement GET /api/v1/admin/tools/logs endpoint
    - Return tool call logs với filtering và pagination
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 7. Authentication và Authorization
  - [ ] 7.1 Implement admin authentication dependency
    - Extend `app/api/deps.py` với get_current_admin
    - Check user role = admin
    - _Requirements: 7.1, 7.2_
  - [ ]* 7.2 Write property test: Auth Enforcement
    - **Property 11: Auth Enforcement**
    - *For any* non-admin request, SHALL return 403. *For any* unauthenticated, SHALL return 401
    - **Validates: Requirements 7.1, 7.2**

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Integration với Unified Agent
  - [ ] 9.1 Integrate ToolRegistry vào UnifiedAgent
    - Modify `app/engine/unified_agent.py`
    - Check is_tool_enabled trước khi gọi tool
    - Record tool calls cho statistics
    - _Requirements: 3.1, 5.1_
  - [ ]* 9.2 Write property test: Disable Prevents Calling
    - **Property 4: Disable Prevents Calling**
    - *For any* disabled tool, UnifiedAgent SHALL NOT invoke that tool
    - **Validates: Requirements 3.1**
  - [ ]* 9.3 Write property test: Config Immediate Effect
    - **Property 8: Config Immediate Effect**
    - *For any* config update, new values SHALL be used in subsequent calls
    - **Validates: Requirements 4.3**

- [ ] 10. Register Router và Final Integration
  - [ ] 10.1 Register admin router trong main.py
    - Add router vào FastAPI app
    - Configure CORS nếu cần
    - _Requirements: All_
  - [ ]* 10.2 Write integration test cho full API flow
    - Test complete flow: list → detail → update → verify
    - _Requirements: All_

- [ ] 11. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
