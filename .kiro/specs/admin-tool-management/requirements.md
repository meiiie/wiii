# Requirements Document

## Introduction

Admin Tool Management API cho phép quản trị viên giám sát và quản lý các AI Tools trong hệ thống Maritime AI Tutor. API này cung cấp khả năng xem trạng thái, bật/tắt, cấu hình và theo dõi thống kê sử dụng của các tools mà Unified Agent sử dụng.

## Glossary

- **Tool**: Một function mà AI Agent có thể gọi để thực hiện tác vụ cụ thể (VD: tra cứu kiến thức, lưu thông tin user)
- **Tool Registry**: Hệ thống quản lý danh sách và trạng thái của tất cả tools
- **Tool Call**: Một lần gọi tool bởi AI Agent
- **Admin**: Người dùng có quyền quản trị hệ thống (role = admin)
- **Tool Config**: Các tham số cấu hình của tool (VD: search_limit, timeout)

## Requirements

### Requirement 1: Xem danh sách Tools

**User Story:** As an admin, I want to view all available AI tools, so that I can understand what capabilities the AI system has.

#### Acceptance Criteria

1. WHEN an admin requests the tool list THEN the System SHALL return all registered tools with their basic information (name, description, enabled status)
2. WHEN displaying tool information THEN the System SHALL include the tool's current configuration parameters
3. WHEN a tool has dependencies (e.g., HybridSearchService) THEN the System SHALL show the dependency status (available/unavailable)

### Requirement 2: Xem chi tiết Tool

**User Story:** As an admin, I want to view detailed information about a specific tool, so that I can understand its configuration and usage.

#### Acceptance Criteria

1. WHEN an admin requests details for a specific tool THEN the System SHALL return complete tool information including name, description, parameters schema, and current config
2. WHEN the requested tool does not exist THEN the System SHALL return a 404 error with descriptive message
3. WHEN displaying tool details THEN the System SHALL include real-time availability status of the tool's dependencies

### Requirement 3: Bật/Tắt Tool

**User Story:** As an admin, I want to enable or disable specific tools, so that I can control AI behavior without redeploying.

#### Acceptance Criteria

1. WHEN an admin disables a tool THEN the System SHALL prevent the AI from calling that tool
2. WHEN an admin enables a previously disabled tool THEN the System SHALL allow the AI to call that tool again
3. WHEN a tool is disabled THEN the System SHALL log the action with admin ID and timestamp
4. WHEN attempting to disable a critical tool (e.g., tool_maritime_search) THEN the System SHALL require confirmation

### Requirement 4: Cấu hình Tool

**User Story:** As an admin, I want to modify tool configuration parameters, so that I can tune AI behavior.

#### Acceptance Criteria

1. WHEN an admin updates tool configuration THEN the System SHALL validate the new values against the parameter schema
2. WHEN configuration values are invalid THEN the System SHALL reject the update and return validation errors
3. WHEN configuration is updated successfully THEN the System SHALL apply changes immediately without restart
4. WHEN configuration is updated THEN the System SHALL log the change with previous and new values

### Requirement 5: Xem thống kê sử dụng

**User Story:** As an admin, I want to view tool usage statistics, so that I can monitor AI behavior and performance.

#### Acceptance Criteria

1. WHEN an admin requests tool statistics THEN the System SHALL return call counts, success rates, and average latency
2. WHEN displaying statistics THEN the System SHALL support time range filtering (today, 7 days, 30 days)
3. WHEN a tool has errors THEN the System SHALL include error counts and common error types

### Requirement 6: Xem lịch sử Tool Calls

**User Story:** As an admin, I want to view recent tool call logs, so that I can debug issues and understand AI decisions.

#### Acceptance Criteria

1. WHEN an admin requests tool call logs THEN the System SHALL return recent calls with timestamp, input, output, and duration
2. WHEN displaying logs THEN the System SHALL support filtering by tool name and time range
3. WHEN displaying logs THEN the System SHALL support pagination (limit, offset)
4. WHEN a tool call failed THEN the System SHALL include the error message in the log entry

### Requirement 7: Bảo mật API

**User Story:** As a system architect, I want the admin API to be secure, so that only authorized admins can manage tools.

#### Acceptance Criteria

1. WHEN a non-admin user attempts to access admin endpoints THEN the System SHALL return 403 Forbidden
2. WHEN an unauthenticated request is made THEN the System SHALL return 401 Unauthorized
3. WHEN admin actions are performed THEN the System SHALL create audit log entries
