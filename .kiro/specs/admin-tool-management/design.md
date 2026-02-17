# Design Document: Admin Tool Management API

## Overview

Admin Tool Management API cung cấp RESTful endpoints cho phép Admin giám sát và quản lý các AI Tools trong hệ thống Maritime AI Tutor. API này tích hợp với Unified Agent để kiểm soát hành vi của AI mà không cần redeploy.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ADMIN DASHBOARD (Future)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ADMIN API LAYER                                      │
│                    /api/v1/admin/tools/*                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ GET /tools  │  │ GET /:name  │  │ PUT /:name  │  │ GET /stats  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TOOL MANAGEMENT SERVICE                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      ToolRegistry (Singleton)                        │   │
│  │  - tools: Dict[str, ToolInfo]                                       │   │
│  │  - get_all_tools() -> List[ToolInfo]                                │   │
│  │  - get_tool(name) -> ToolInfo                                       │   │
│  │  - enable_tool(name) / disable_tool(name)                           │   │
│  │  - update_config(name, config)                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│   Tool Stats Repository │ │   Tool Logs Repository  │ │   Audit Log Repository  │
│   (In-memory + Supabase)│ │   (Supabase)            │ │   (Supabase)            │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

## Components and Interfaces

### 1. API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/admin/tools` | List all tools | Admin |
| GET | `/api/v1/admin/tools/{name}` | Get tool details | Admin |
| PUT | `/api/v1/admin/tools/{name}` | Update tool (enable/disable/config) | Admin |
| GET | `/api/v1/admin/tools/stats` | Get usage statistics | Admin |
| GET | `/api/v1/admin/tools/logs` | Get tool call logs | Admin |

### 2. ToolRegistry Class

```python
class ToolRegistry:
    """Singleton registry for managing AI tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._stats: Dict[str, ToolStats] = {}
    
    def register_tool(self, tool: BaseTool, config: ToolConfig) -> None:
        """Register a tool with its configuration."""
    
    def get_all_tools(self) -> List[ToolInfo]:
        """Get all registered tools."""
    
    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """Get a specific tool by name."""
    
    def enable_tool(self, name: str, admin_id: str) -> bool:
        """Enable a tool."""
    
    def disable_tool(self, name: str, admin_id: str, confirm: bool = False) -> bool:
        """Disable a tool. Critical tools require confirm=True."""
    
    def update_config(self, name: str, config: Dict, admin_id: str) -> bool:
        """Update tool configuration."""
    
    def record_call(self, name: str, input: Dict, output: str, duration_ms: int, success: bool) -> None:
        """Record a tool call for statistics."""
    
    def is_tool_enabled(self, name: str) -> bool:
        """Check if a tool is enabled."""
```

### 3. ToolInfo Model

```python
@dataclass
class ToolInfo:
    name: str
    description: str
    enabled: bool
    is_critical: bool
    config: Dict[str, Any]
    config_schema: Dict[str, Any]  # JSON Schema for validation
    dependencies: List[str]
    dependency_status: Dict[str, bool]
    
@dataclass
class ToolStats:
    name: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    avg_latency_ms: float
    last_called: Optional[datetime]
    error_types: Dict[str, int]

@dataclass
class ToolCallLog:
    id: str
    tool_name: str
    timestamp: datetime
    input_args: Dict
    output: str
    duration_ms: int
    success: bool
    error_message: Optional[str]
    user_id: str
    session_id: str
```

## Data Models

### Tool Configuration Schema

```json
{
  "tool_maritime_search": {
    "search_limit": {"type": "integer", "min": 1, "max": 20, "default": 5},
    "use_hybrid_search": {"type": "boolean", "default": true},
    "timeout_seconds": {"type": "integer", "min": 5, "max": 60, "default": 30}
  },
  "tool_save_user_info": {
    "max_facts_per_user": {"type": "integer", "min": 10, "max": 100, "default": 50}
  },
  "tool_get_user_info": {
    "include_semantic_memory": {"type": "boolean", "default": true}
  }
}
```

### Database Tables

```sql
-- Tool call logs (for statistics and debugging)
CREATE TABLE tool_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    input_args JSONB,
    output TEXT,
    duration_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tool_logs_name ON tool_call_logs(tool_name);
CREATE INDEX idx_tool_logs_timestamp ON tool_call_logs(timestamp);

-- Admin audit logs
CREATE TABLE admin_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,  -- 'enable_tool', 'disable_tool', 'update_config'
    target_tool VARCHAR(100),
    old_value JSONB,
    new_value JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Tool List Completeness
*For any* valid admin request to list tools, the response SHALL contain all registered tools with name, description, enabled status, and config fields.
**Validates: Requirements 1.1, 1.2**

### Property 2: Tool Detail Accuracy
*For any* existing tool name, requesting details SHALL return complete information including dependencies and their availability status.
**Validates: Requirements 2.1, 2.3**

### Property 3: Non-existent Tool Returns 404
*For any* tool name that is not registered, requesting details SHALL return HTTP 404.
**Validates: Requirements 2.2**

### Property 4: Disable Prevents Calling
*For any* disabled tool, the Unified Agent SHALL NOT be able to invoke that tool.
**Validates: Requirements 3.1**

### Property 5: Enable-Disable Round Trip
*For any* tool, disabling then enabling SHALL restore the tool to callable state.
**Validates: Requirements 3.2**

### Property 6: Action Logging
*For any* admin action (enable, disable, config update), an audit log entry SHALL be created with admin ID, timestamp, and action details.
**Validates: Requirements 3.3, 4.4**

### Property 7: Config Validation
*For any* configuration update with invalid values (outside schema bounds), the System SHALL reject with validation errors.
**Validates: Requirements 4.1, 4.2**

### Property 8: Config Immediate Effect
*For any* successful configuration update, the new values SHALL be used in subsequent tool calls without restart.
**Validates: Requirements 4.3**

### Property 9: Stats Completeness
*For any* statistics request, the response SHALL include call counts, success rate, and average latency for each tool.
**Validates: Requirements 5.1, 5.3**

### Property 10: Log Pagination
*For any* log request with limit L and offset O, the response SHALL return at most L entries starting from position O.
**Validates: Requirements 6.3**

### Property 11: Auth Enforcement
*For any* request without admin role, the System SHALL return 403 Forbidden. *For any* unauthenticated request, the System SHALL return 401 Unauthorized.
**Validates: Requirements 7.1, 7.2**

## Error Handling

| Error Code | Condition | Response |
|------------|-----------|----------|
| 400 | Invalid config values | `{"error": "validation_error", "details": [...]}` |
| 401 | No authentication | `{"error": "unauthorized"}` |
| 403 | Non-admin user | `{"error": "forbidden", "message": "Admin access required"}` |
| 404 | Tool not found | `{"error": "not_found", "message": "Tool 'x' not found"}` |
| 409 | Critical tool disable without confirm | `{"error": "confirmation_required", "message": "..."}` |

## Testing Strategy

### Unit Tests
- ToolRegistry CRUD operations
- Config validation logic
- Stats calculation

### Property-Based Tests (Hypothesis)
- Property 1-11 as defined above
- Use `hypothesis` library for Python
- Minimum 100 iterations per property

### Integration Tests
- Full API flow with authentication
- Database persistence verification
