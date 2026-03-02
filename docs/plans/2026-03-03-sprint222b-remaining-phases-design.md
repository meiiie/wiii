# Sprint 222b: Complete Universal Context Engine — Remaining Phases

> **Sprint**: 222b
> **Date**: 2026-03-03
> **Status**: Design complete, pending implementation
> **Prerequisite**: Sprint 222 Phases 1-4 (IMPLEMENTED)
> **Author**: Claude Code (LEADER)

---

## 1. Overview

Sprint 222 Phases 1-4 implemented the read-only host context engine (HostContext models, adapters, graph-level injection, frontend store). This document covers the three remaining pieces:

| Piece | What | Mode |
|-------|------|------|
| **Phase 5** | Bidirectional PostMessage Actions | Iframe embed |
| **Phase 6** | Dynamic YAML Skill Loading | Both modes |
| **Phase 7** | Standalone Browser Agent | Desktop app |

---

## 2. Research Summary (SOTA March 2026)

### Browser Automation Patterns

| System | Approach | Protocol | Best For |
|--------|----------|----------|----------|
| Anthropic Computer Use | Screenshot + pixel | Native API | Full desktop control |
| OpenAI CUA | Screenshot loop | Responses API | Web-only (cloud) |
| Google Mariner | Screenshot + DOM | Chrome extension | Consumer browsing |
| Browser-Use | DOM extraction + Playwright | LangChain tools | LangGraph integration |
| Stagehand v3 | CDP-native + a11y tree | TypeScript SDK | Fast, AI-native |
| Playwright MCP | Accessibility tree | MCP (stdio/http) | Token-efficient, structured |
| Microsoft Copilot | API connectors | Graph API | Enterprise workflows |
| Alibaba OpenSandbox | Docker sandbox | REST API | Safe code/browser exec |

### Key Decision: Playwright MCP for Wiii

**Why:** Accessibility-tree approach uses ~3K tokens/turn (vs 10K for screenshots), Wiii already has MCPToolManager (Sprint 194) and Playwright infrastructure (Sprint 152-154). Fits naturally into existing LangGraph agent loop.

**Not screenshot-based:** Overkill for structured web tasks. Screenshot approach reserved for future "full desktop control" feature.

---

## 3. Phase 5: Bidirectional PostMessage Actions

### 3.1 Architecture

```
User: "Tạo khóa học An toàn hàng hải"
  → Supervisor routes to agent
  → Agent calls tool_host_action("create_course", {name: "..."})
  → HostActionBridge validates (role + capability check)
  → Emits SSE event: {type: "host_action", id: "req-001", action: "create_course", params: {...}}
  → Frontend receives SSE → sends PostMessage to host:
      {type: "wiii:action-request", id: "req-001", action: "create_course", params: {...}}
  → Host executes → confirms:
      {type: "wiii:action-response", id: "req-001", result: {success: true, data: {...}}}
  → Frontend resolves promise → sends confirmation in next chat turn
  → AI confirms to user: "Đã tạo khóa học 'An toàn hàng hải' thành công!"
```

### 3.2 Backend Components

#### `action_bridge.py` — HostActionBridge

```python
class HostActionBridge:
    """Manages bidirectional action requests between AI and host.

    Receives tool calls from LLM agents, validates against host capabilities,
    and emits SSE events for frontend to forward via PostMessage.
    """

    def create_action_tool(self, action_def: dict) -> StructuredTool:
        """Generate a LangChain StructuredTool from a host-declared action.

        action_def from HostCapabilities.tools[]:
        {
            "name": "create_course",
            "description": "Create a new course",
            "input_schema": {"type": "object", "properties": {...}},
            "roles": ["teacher", "admin"]
        }
        """

    def validate_action(self, action: str, params: dict,
                        user_role: str, adapter: HostAdapter) -> bool:
        """Role-based validation before emitting action request."""

    def emit_action_request(self, action: str, params: dict,
                            event_bus_id: str) -> str:
        """Emit SSE host_action event. Returns request_id for tracking."""
```

#### `action_tools.py` — Dynamic Tool Generation

```python
def generate_host_action_tools(capabilities: HostCapabilities,
                                user_role: str) -> list[StructuredTool]:
    """Generate LangChain tools from host-declared actions.

    Filters by user role. Only creates tools the user is allowed to execute.
    Tools call HostActionBridge.emit_action_request() when invoked.
    """
```

#### `stream_utils.py` — New SSE Event Type

```python
def create_host_action_event(request_id: str, action: str,
                              params: dict) -> StreamEvent:
    """SSE event for host action requests (Wiii → host via frontend)."""
    return StreamEvent(
        type="host_action",
        content={
            "id": request_id,
            "action": action,
            "params": params,
        }
    )
```

### 3.3 Frontend Components

#### `host-context-store.ts` — Action Support

```typescript
// Add to existing store:
pendingActions: Map<string, {
  resolve: (result: ActionResult) => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
}>;

requestAction: (action: string, params: Record<string, unknown>) => Promise<ActionResult>;
resolveAction: (requestId: string, result: ActionResult) => void;
```

**requestAction flow:**
1. Generate UUID request_id
2. Send PostMessage `wiii:action-request` to parent
3. Create Promise, store in pendingActions map
4. Set 30s timeout → reject if no response
5. Return Promise (resolved when host responds)

#### `useSSEStream.ts` — Handle host_action Events

```typescript
case 'host_action':
  const { id, action, params } = event.content;
  useHostContextStore.getState().requestAction(action, params)
    .then(result => {
      // Result available — could send in next message or store
    })
    .catch(err => {
      // Timeout or host error
    });
  break;
```

#### `EmbedApp.tsx` — Action Response Handler

```typescript
case 'wiii:action-response':
  useHostContextStore.getState().resolveAction(
    event.data.id, event.data.result
  );
  break;
```

### 3.4 Feature Gate

```python
enable_host_actions: bool = False  # Already exists from Phase 4
```

---

## 4. Phase 6: Dynamic YAML Skill Loading

### 4.1 Architecture

```
Graph entry: _inject_host_context(state)
  → get_host_adapter(host_type).get_page_skill_ids(ctx)
  → ContextSkillLoader.load_skills(host_type, page_type)
  → Returns list[ContextSkill]:
      - prompt_addition: str (appended to host_context_prompt)
      - tool_ids: list[str] (tools to activate)
      - enrichment_triggers: list[dict] (auto-request patterns)
  → prompt_addition appended to XML block
  → tool_ids used for IntelligentToolSelector filtering
```

### 4.2 Skill YAML Format

Following Claude Code's SKILL.md progressive disclosure pattern:

```yaml
# app/engine/context/skills/lms/quiz.skill.yaml
name: lms-quiz
host_type: lms
page_types: [quiz, exam]
description: "Socratic quiz guidance — never reveal answers"
priority: 1.0

prompt_addition: |
  QUAN TRỌNG: Sinh viên đang làm bài kiểm tra.
  - KHÔNG cho đáp án trực tiếp
  - Hướng dẫn Socratic: gợi mở để sinh viên suy nghĩ
  - Nếu đã sai 3+ lần → có thể gợi ý rõ hơn
  - Nếu sinh viên hỏi về nội dung liên quan → dùng tool tìm kiếm

tools:
  - tool_knowledge_search
  - tool_explain_concept

enrichment_triggers:
  - pattern: "giải thích|explain|tại sao|why"
    action: request_content_snippet
```

### 4.3 Skill Loader

```python
class ContextSkillLoader:
    """Load YAML skills based on host_type + page_type.

    Follows Claude Code's progressive disclosure:
    - Metadata always scanned at startup (name + description)
    - Full skill loaded only when page matches

    Fallback chain:
    1. Exact: {host_type}/{page_type}.skill.yaml
    2. Generic page: generic/{page_type}.skill.yaml
    3. Host default: {host_type}/default.skill.yaml
    4. Global default: generic/default.skill.yaml
    """

    _skills_dir: Path  # app/engine/context/skills/
    _cache: dict[str, list[ContextSkill]]  # keyed by "host_type:page_type"

    def load_skills(self, host_type: str, page_type: str) -> list[ContextSkill]:
        """Return matching skills sorted by priority."""

    def get_prompt_addition(self, skills: list[ContextSkill]) -> str:
        """Concatenate prompt_additions from all active skills."""

    def get_tool_ids(self, skills: list[ContextSkill]) -> list[str]:
        """Return tool IDs from all active skills."""
```

### 4.4 Skill Files to Create

| File | Host | Page Types | Key Behavior |
|------|------|-----------|--------------|
| `lms/lesson.skill.yaml` | lms | lesson, course_overview | Socratic teaching, content reference |
| `lms/quiz.skill.yaml` | lms | quiz, exam | NEVER reveal answers, gợi mở |
| `lms/assignment.skill.yaml` | lms | assignment | Guide methodology, not solutions |
| `lms/course.skill.yaml` | lms | course_list, course_overview | Course recommendations |
| `lms/default.skill.yaml` | lms | * | General LMS behavior |
| `generic/default.skill.yaml` | * | * | Universal fallback |

### 4.5 Integration with Graph

In `_inject_host_context()`, after adapter formats the prompt:

```python
# Phase 6: Load skills if enabled
if getattr(settings, "enable_host_skills", False):
    from app.engine.context.skill_loader import get_skill_loader
    loader = get_skill_loader()
    skills = loader.load_skills(host_ctx.host_type, page_type)
    prompt_addition = loader.get_prompt_addition(skills)
    if prompt_addition:
        formatted_prompt += "\n\n" + prompt_addition
```

### 4.6 Feature Gate

```python
enable_host_skills: bool = False  # Already exists from Phase 4
```

---

## 5. Phase 7: Standalone Browser Agent (Wiii Desktop)

### 5.1 Architecture

When Wiii runs as a standalone Tauri desktop app (NOT iframe-embedded), it can browse the web autonomously:

```
User in Wiii Desktop: "Tìm giá vé máy bay HN-SG ngày mai"
  → Supervisor routes to Direct agent
  → Direct agent has browser tools (from Playwright MCP)
  → Agent calls browser_navigate("https://vietnamairlines.com")
  → MCPToolManager → Playwright MCP server (local process)
  → Playwright opens Chrome, navigates
  → Agent calls browser_snapshot() → gets accessibility tree
  → Agent reasons about page structure
  → Agent calls browser_click("search button")
  → Agent calls browser_fill_form({from: "HAN", to: "SGN", date: "..."})
  → Agent calls browser_snapshot() → reads results
  → Agent synthesizes: "Giá vé từ 1.2tr đến 3.5tr..."
```

### 5.2 Implementation: Backend-Driven Pattern

**Why backend-driven (not Tauri sidecar):**
- Wiii already has Playwright infrastructure (Sprint 152-154)
- MCPToolManager already consumes MCP servers (Sprint 194)
- SSE streaming works for long-running browser tasks
- No deployment complexity (no bundled Node.js binaries)
- Sidecar can be added later for offline/local mode

**Components:**

#### Config additions

```python
# app/core/config.py
enable_browser_agent: bool = False
browser_agent_mcp_command: str = "npx"
browser_agent_mcp_args: list[str] = ["@playwright/mcp", "--headless"]
browser_agent_timeout: int = 120  # seconds per browser session
```

#### MCP Server Configuration

```python
# Added to MCPToolManager server list when enable_browser_agent=True
{
    "name": "playwright",
    "command": settings.browser_agent_mcp_command,
    "args": settings.browser_agent_mcp_args,
    "transport": "stdio",
}
```

#### Tool Registration

When `enable_browser_agent=True`, MCPToolManager discovers and registers Playwright MCP tools:
- `browser_navigate` — Go to URL
- `browser_snapshot` — Get accessibility tree
- `browser_click` — Click element
- `browser_type` — Type text
- `browser_fill_form` — Fill form fields
- `browser_press_key` — Keyboard input
- `browser_select_option` — Select dropdown
- `browser_take_screenshot` — Visual capture
- `browser_wait_for` — Wait for element
- `browser_tabs` — Tab management

These tools are auto-registered into the ToolRegistry via `register_discovered_tools()` (Sprint 194).

### 5.3 Safety & Limits

- **URL validation**: Block private IPs (existing SSRF prevention from Sprint 153)
- **Session timeout**: 120s max per browser session
- **Headless by default**: `--headless` flag (user can override in config)
- **No authentication forwarding**: Browser agent does NOT use user's cookies/credentials
- **Rate limiting**: Max 10 browser sessions per user per hour

### 5.4 Feature Gate

```python
enable_browser_agent: bool = False  # New
```

---

## 6. Testing Strategy

### Phase 5 Tests (~25)

- HostActionBridge: tool generation, validation, emit, timeout
- Dynamic tool creation from HostCapabilities
- SSE host_action event format
- Frontend: requestAction/resolveAction flow
- Role-based action filtering

### Phase 6 Tests (~20)

- SkillLoader: YAML parsing, priority, fallback chain
- Skill prompt_addition formatting
- Tool ID extraction from skills
- Integration with _inject_host_context
- Enrichment trigger pattern matching

### Phase 7 Tests (~15)

- Config flag gating
- MCP server configuration
- Tool registration verification
- URL validation (SSRF prevention)
- Session timeout enforcement

### Total: ~60 new tests

---

## 7. Implementation Order

```
Phase 6 (Skills) ← Foundation, no external deps
  ↓
Phase 5 (Actions) ← Needs skills for context
  ↓
Phase 7 (Browser) ← Independent, can be parallel with 5
  ↓
Full regression + rebuild
```

**Rationale:** Phase 6 (skills) is pure internal code with no external dependencies — safest to build first. Phase 5 (actions) requires frontend↔backend coordination. Phase 7 (browser) requires Playwright MCP to be installed.

---

## 8. Migration Notes

- Sprint 221's `page-context-store.ts` can be deprecated after Sprint 222b
- Existing `format_page_context_for_prompt()` in `prompt_loader.py` is superseded by LMSHostAdapter but kept for backward compat
- `enable_browser_scraping` (Sprint 152) remains separate from `enable_browser_agent` — scraping is product-search-specific, browser agent is general-purpose
