# Design Document: API Transparency & Thinking

## Overview

Cải tiến API response để tăng tính minh bạch và đảm bảo AI luôn suy luận trước khi trả lời câu hỏi kiến thức. Hai thay đổi chính:

1. **Expose `tools_used`**: Thêm field vào `ChatResponseMetadata` để LMS biết AI đã dùng tool gì
2. **Mandatory `<thinking>` for RAG**: Cập nhật SYSTEM_PROMPT để bắt buộc AI suy luận khi tra cứu kiến thức

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
│  ChatResponse                                                    │
│  ├── data: ChatResponseData                                      │
│  │   ├── answer (with <thinking> tag for RAG)                   │
│  │   ├── sources                                                 │
│  │   └── suggested_questions                                     │
│  └── metadata: ChatResponseMetadata                              │
│      ├── processing_time                                         │
│      ├── model                                                   │
│      ├── agent_type                                              │
│      └── tools_used: List[ToolUsageInfo]  ← NEW                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     UnifiedAgent                                 │
│  ├── SYSTEM_PROMPT (updated with <thinking> rules)              │
│  ├── _manual_react() → returns tools_used                       │
│  └── process() → passes tools_used to response                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Schema Changes (schemas.py)

```python
class ToolUsageInfo(BaseModel):
    """Information about a tool that was used during processing."""
    name: str = Field(..., description="Tên tool đã gọi")
    description: str = Field(default="", description="Mô tả ngắn về kết quả")

class ChatResponseMetadata(BaseModel):
    """Metadata in chat response - UPDATED"""
    processing_time: float
    model: str = "maritime-rag-v1"
    agent_type: AgentType = AgentType.RAG
    session_id: Optional[str] = None  # Already exists
    tools_used: List[ToolUsageInfo] = Field(
        default_factory=list, 
        description="Danh sách tools đã sử dụng"
    )  # NEW
```

### 2. SYSTEM_PROMPT Update (unified_agent.py)

Thêm quy tắc bắt buộc `<thinking>` cho RAG queries:

```
⚠️ QUY TẮC BẮT BUỘC VỀ SUY LUẬN (<thinking>):

1. KHI TRA CỨU KIẾN THỨC (gọi tool_maritime_search):
   → PHẢI bắt đầu response bằng <thinking>
   → Trong <thinking>, giải thích:
     - User đang hỏi về gì?
     - Kết quả tra cứu cho thấy điều gì?
     - Cách tổng hợp thông tin để trả lời
   → Sau </thinking>, mới đưa ra câu trả lời

2. KHI TRẢ LỜI TRỰC TIẾP (không cần tool):
   → <thinking> là TÙY CHỌN
   → Có thể dùng khi cần suy nghĩ về cách phản hồi

VÍ DỤ:
User: "Giải thích Rule 15"
→ Gọi tool_maritime_search("Rule 15 COLREGs")
→ Response:
<thinking>
User hỏi về Rule 15 COLREGs - quy tắc về tình huống cắt hướng.
Kết quả tra cứu cho thấy Rule 15 quy định khi hai tàu máy cắt hướng,
tàu nhìn thấy tàu kia ở mạn phải phải nhường đường.
Tôi sẽ giải thích rõ ràng với ví dụ thực tế.
</thinking>

Theo Điều 15 COLREGs về tình huống cắt hướng...
```

### 3. Chat Service Changes (chat_service.py)

Truyền `tools_used` từ UnifiedAgent vào response metadata:

```python
# In process_message():
unified_result = await self._unified_agent.process(...)

# Build metadata with tools_used
metadata = {
    "unified_agent": True,
    "tools_used": unified_result.get("tools_used", []),  # Already exists internally
    "iterations": unified_result.get("iterations", 1)
}
```

### 4. API Endpoint Changes (chat.py)

Format `tools_used` cho API response:

```python
# In chat_endpoint():
tools_used_info = []
if internal_tools := response.metadata.get("tools_used", []):
    for tool in internal_tools:
        tools_used_info.append(ToolUsageInfo(
            name=tool.get("name", "unknown"),
            description=_get_tool_description(tool)
        ))

metadata = ChatResponseMetadata(
    processing_time=processing_time,
    agent_type=response.agent_type,
    session_id=str(session_id),
    tools_used=tools_used_info  # NEW
)
```

## Data Models

### ToolUsageInfo

| Field | Type | Description |
|-------|------|-------------|
| name | str | Tên tool (tool_maritime_search, tool_save_user_info, tool_get_user_info) |
| description | str | Mô tả ngắn về kết quả (e.g., "Tra cứu Rule 15 COLREGs") |

### Updated ChatResponseMetadata

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| processing_time | float | required | Thời gian xử lý (giây) |
| model | str | "maritime-rag-v1" | Model AI |
| agent_type | AgentType | RAG | Agent xử lý |
| session_id | str | None | Session ID |
| tools_used | List[ToolUsageInfo] | [] | **NEW** - Tools đã sử dụng |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: API response always contains valid tools_used array

*For any* API response from the chat endpoint, the `metadata.tools_used` field SHALL be a valid JSON array (empty or with ToolUsageInfo objects).

**Validates: Requirements 1.1, 1.4**

### Property 2: Empty tools_used for non-tool responses

*For any* message that does not trigger tool calls (greetings, empathy), the `tools_used` array SHALL be empty.

**Validates: Requirements 1.2**

### Property 3: Tool entries contain required fields

*For any* entry in `tools_used` array, it SHALL contain both `name` (non-empty string) and `description` (string) fields.

**Validates: Requirements 1.3**

### Property 4: RAG responses include thinking tag

*For any* response where `tool_maritime_search` was called, the `answer` field SHALL contain a `<thinking>` tag.

**Validates: Requirements 2.1**

### Property 5: Backward compatibility maintained

*For any* API response, the existing fields (`data.answer`, `data.sources`, `data.suggested_questions`) SHALL be present and maintain their original types.

**Validates: Requirements 3.1, 3.3**

## Error Handling

1. **Tool execution fails**: `tools_used` still includes the tool with error description
2. **Thinking tag missing**: Log warning but don't fail the request (graceful degradation)
3. **Schema validation**: Pydantic validates `tools_used` structure automatically

## Testing Strategy

### Unit Tests
- Test `ToolUsageInfo` schema validation
- Test `ChatResponseMetadata` with and without `tools_used`
- Test SYSTEM_PROMPT contains thinking rules

### Property-Based Tests (fast-check/Hypothesis)
- Property 1: Generate random responses, verify tools_used is valid array
- Property 2: Generate non-tool messages, verify empty tools_used
- Property 3: Generate tool responses, verify entry structure
- Property 4: Generate RAG queries, verify thinking tag presence
- Property 5: Generate any response, verify backward compatibility

### Integration Tests
- Test full flow: RAG query → tools_used populated → thinking tag present
- Test full flow: Greeting → tools_used empty → thinking optional
