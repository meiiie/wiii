# Page-Aware AI v2 — "Wiii Universal Context Engine"

> **Sprint**: 222 (planned)
> **Date**: 2026-03-03
> **Status**: Design approved, pending implementation
> **Author**: Claude Code (LEADER)

---

## 1. Problem Statement

Sprint 221 implemented a PostMessage bridge for LMS page context. The bridge works
(E2E verified: PostMessage delivered, stored in Zustand, sent in ChatRequest payload).
However:

1. **Bug**: Only `graph.py` (direct_agent) and `tutor_node.py` inject `page_context`
   into the system prompt. `memory_agent` — where personal/context questions get
   routed — does NOT include it. The AI "guesses" instead of "knowing".

2. **Architecture gap**: Page context injection is scattered per-agent. Adding a new
   agent means remembering to add page_context — fragile and error-prone.

3. **Read-only**: Wiii can only READ context from the host. Cannot navigate, create
   resources, or execute actions ("Tạo khóa học giúp tôi" is impossible).

4. **LMS-specific**: The schema uses LMS-specific fields (`course_id`, `lesson_id`).
   Wiii needs to embed in ANY host app (e-commerce, trading, CRM, ...).

---

## 2. Design Goals

| Goal | Description |
|------|-------------|
| **Accurate** | AI must KNOW exactly what page the user is on, not guess |
| **Bidirectional** | Read context IN + execute actions OUT |
| **Host-agnostic** | Same protocol for LMS, e-commerce, trading, CRM |
| **MCP-compatible** | Schema follows MCP Resource/Tool conventions |
| **Progressive** | Start simple (PostMessage), evolve to full MCP |
| **Extensible** | Add new host types via adapter + YAML skills |

---

## 3. Research Summary (SOTA March 2026)

### Industry Patterns

| System | Context Approach | Action Approach |
|--------|-----------------|----------------|
| Khanmigo (Khan Academy) | Structured injection (internal API) | N/A (read-only) |
| Duolingo Max | Server-side state assembly | N/A (read-only) |
| Microsoft Copilot M365 | Graph API + Semantic Index | Microsoft Graph write APIs |
| Gemini Chrome (Mariner) | DOM + Screenshot (extension API) | Extension API actions |
| MCP Specification | Resources (app-controlled) | Tools (model-controlled) |
| OpenAI Agents SDK | RunContextWrapper (typed state) | Function calling |
| Claude Code Skills | SKILL.md (progressive disclosure) | Tool access per skill |
| Zendesk Web Widget | PostMessage + SDK | PostMessage actions |

### Key Findings

1. **Playwright is NOT suitable** for iframe-embedded context awareness (cannot access
   parent DOM, wrong abstraction, no industry precedent).
2. **PostMessage is the industry standard** for iframe↔host communication (Zendesk,
   Intercom, MCP Apps specification).
3. **MCP Resources + Tools** map perfectly to context (read) + actions (write).
4. **Claude Code SKILL.md** pattern proves progressive disclosure works:
   metadata always loaded, full instructions on activation, resources on demand.
5. **Bidirectional PostMessage** enables action execution without browser automation —
   faster, more secure, permission-aware.

---

## 4. Architecture

### 4.1 Two-Layer Model

```
┌──────────────────────────────────────────────────────────┐
│  ANY Host Application (LMS, E-commerce, Trading, CRM)    │
│                                                           │
│  Layer A: Declared Context (host → Wiii)                  │
│  ── Fast, structured, host TELLS Wiii what's on screen    │
│                                                           │
│  Layer B: Action Execution (Wiii → host)                  │
│  ── Wiii ASKS host to navigate, create, submit, etc.      │
│                                                           │
│  On iframe load: sends capability declaration              │
└───────────────────────┬──────────────────────────────────┘
                        │ PostMessage (bidirectional)
                        │ OR MCP protocol (future)
                        ▼
┌──────────────────────────────────────────────────────────┐
│  Wiii Universal Context Engine                            │
│                                                           │
│  1. HostContextStore    ← context updates (Layer A)       │
│  2. HostCapabilityReg   ← available actions declared      │
│  3. HostAdapter         ← interprets per host type        │
│  4. ContextSkillLoader  ← loads skills per page type      │
│  5. HostActionBridge    → sends action requests (Layer B) │
│  6. PromptAssembler     ← XML-tagged context blocks       │
│  7. EnrichmentEngine    ← asks host for more detail       │
└──────────────────────────────────────────────────────────┘
```

### 4.2 PostMessage Protocol

#### Messages: Host → Wiii

```typescript
// Capability declaration (sent once on iframe load)
{
  type: "wiii:capabilities",
  payload: {
    host_type: "lms",
    host_name: "Maritime Academy LMS",
    resources: ["current-page", "user-profile", "course-content"],
    tools: [
      { name: "navigate", description: "Navigate to a page",
        inputSchema: { type: "object", properties: { url: { type: "string" } } } },
      { name: "create_course", description: "Create a new course",
        inputSchema: { ... }, roles: ["teacher", "admin"] },
    ]
  }
}

// Context update (sent on every navigation)
{
  type: "wiii:context",
  resource_uri: "host://current-page",
  payload: {
    page: { type: "lesson", title: "COLREGs Rule 14", url: "/course/123/lesson/5",
            metadata: { course_id: "123", lesson_id: "5" } },
    user_state: { scroll_percent: 45, time_on_page_ms: 30000 },
    content: { snippet: "Khi hai tàu gặp nhau đối hướng..." }
  }
}

// Action response
{
  type: "wiii:action-response",
  id: "req-001",
  result: { success: true, data: { course_id: "abc-123" } }
}

// Enrichment response
{
  type: "wiii:enrich-response",
  id: "enr-001",
  payload: { content_snippet: "Full lesson text here...", exercises: [...] }
}
```

#### Messages: Wiii → Host

```typescript
// Action request
{
  type: "wiii:action-request",
  id: "req-001",
  action: "create_course",
  params: { name: "An toàn hàng hải", description: "..." }
}

// Enrichment request (ask host for more context)
{
  type: "wiii:enrich-request",
  id: "enr-001",
  request_type: "content_snippet" | "exercises" | "full_page"
}
```

### 4.3 MCP Compatibility

The PostMessage protocol is designed to map 1:1 to MCP primitives:

| PostMessage | MCP Equivalent |
|-------------|---------------|
| `wiii:capabilities` | `initialize` response (capabilities) |
| `wiii:context` | `resources/read` response |
| `wiii:action-request` | `tools/call` request |
| `wiii:action-response` | `tools/call` response |
| `wiii:enrich-request` | `resources/read` request (dynamic URI) |

When a host upgrades from PostMessage to full MCP server, the Wiii Context Engine
connects via MCP client without changing its internal architecture.

### 4.4 Generic HostContext Schema

```typescript
interface HostContext {
  // MCP Resource metadata
  resource_uri: string;        // "host://current-page"
  updated_at?: string;         // ISO timestamp

  // Host identity
  host_type: string;           // "lms" | "ecommerce" | "trading" | "crm" | "custom"
  host_name?: string;

  // Current page (always present)
  page: {
    type: string;              // Host-specific: "lesson" | "product" | "chart"
    title?: string;
    url?: string;              // Path only (no origin)
    content_type?: string;
    metadata?: Record<string, any>;
  };

  // User state on page
  user_state?: Record<string, any>;

  // Available actions (MCP Tool-compatible)
  available_actions?: Array<{
    action: string;
    label: string;
    input_schema?: any;        // JSON Schema
    roles?: string[];          // Which user roles can execute
  }>;

  // Content snapshot
  content?: {
    snippet?: string;          // Max 2000 chars
    structured?: any;          // Host-specific data
  };

  // Enrichment capabilities
  enrichment?: {
    supports_request: boolean;
    available_types: string[];  // ["content_snippet", "exercises", "full_page"]
  };
}
```

---

## 5. Host Adapter System

### 5.1 Adapter Registry

```
app/engine/context/
├── __init__.py
├── host_context.py           # HostContext Pydantic model
├── host_context_store.py     # Zustand-equivalent (backend state)
├── host_capability_registry.py  # Tracks available actions
├── host_action_bridge.py     # Sends action requests to host
├── prompt_assembler.py       # XML-tagged context for system prompt
├── enrichment_engine.py      # Requests more detail from host
└── adapters/
    ├── __init__.py
    ├── base.py               # HostAdapter ABC
    ├── lms.py                # LMS-specific interpretation
    ├── ecommerce.py          # E-commerce (future)
    ├── trading.py            # Trading platform (future)
    └── generic.py            # Fallback for unknown host types
```

### 5.2 Adapter Interface

```python
class HostAdapter(ABC):
    host_type: str

    @abstractmethod
    def format_context_for_prompt(self, ctx: HostContext) -> str:
        """Returns XML-tagged context block for system prompt.
        Called ONCE at graph level — ALL agents receive it."""

    @abstractmethod
    def get_page_skill_ids(self, ctx: HostContext) -> list[str]:
        """Returns skill IDs to load for this host+page combo."""

    @abstractmethod
    def get_available_tools(self, ctx: HostContext) -> list[ToolDefinition]:
        """Returns host-action tools available for this context."""

    @abstractmethod
    def validate_action(self, action: str, params: dict, user_role: str) -> bool:
        """Validates if user can execute this action (role-based)."""
```

### 5.3 LMS Adapter Example

```python
class LMSHostAdapter(HostAdapter):
    host_type = "lms"

    def format_context_for_prompt(self, ctx):
        page = ctx.page
        parts = ["<host_context type=\"lms\">"]
        parts.append(f"  <page type=\"{page.type}\">{page.title or ''}</page>")

        if page.metadata:
            if page.metadata.get("course_name"):
                parts.append(f"  <course>{page.metadata['course_name']}</course>")

        if ctx.content and ctx.content.get("snippet"):
            parts.append(f"  <content>{ctx.content['snippet']}</content>")

        # Page-type-specific instructions
        if page.type == "quiz":
            parts.append("  <instruction>KHÔNG cho đáp án trực tiếp. Socratic method.</instruction>")
        elif page.type == "lesson":
            parts.append("  <instruction>Hỗ trợ sinh viên hiểu bài giảng.</instruction>")

        parts.append("</host_context>")
        return "\n".join(parts)
```

---

## 6. Dynamic Skill System (SKILL.md Pattern)

### 6.1 Skill File Format

Following Claude Code's SKILL.md pattern adapted for host context:

```yaml
# app/engine/context/skills/lms/lesson.skill.yaml
name: lms-lesson
host_type: lms
page_types: [lesson, course_overview]
description: "Tutoring skills for lesson pages"
priority: 1.0

# Additional system prompt for this context
prompt_addition: |
  Sinh viên đang xem bài giảng. Dùng phương pháp Socratic.
  Tham chiếu nội dung bài học khi trả lời.
  Nếu sinh viên hỏi về nội dung trang → dùng tool_get_page_content().

# Tools available in this context
tools:
  - tool_knowledge_search
  - tool_explain_concept
  - tool_generate_practice_quiz
  - tool_summarize_lesson

# Enrichment triggers (auto-fetch content when pattern matches)
enrichment_triggers:
  - pattern: "giải thích|explain|nội dung|đang đọc"
    action: request_content_snippet
  - pattern: "bài tập|exercise|practice|luyện tập"
    action: request_exercises
```

```yaml
# app/engine/context/skills/lms/quiz.skill.yaml
name: lms-quiz
host_type: lms
page_types: [quiz, exam]
description: "Socratic quiz guidance"
priority: 1.0

prompt_addition: |
  QUAN TRỌNG: KHÔNG cho đáp án trực tiếp.
  Hướng dẫn Socratic: gợi mở để sinh viên suy nghĩ.
  Nếu sinh viên sai 3+ lần → gợi ý rõ hơn.

tools:
  - tool_knowledge_search
  - tool_explain_concept
  # NO tool_generate_quiz (already in a quiz!)
```

### 6.2 Skill Loader

```python
class ContextSkillLoader:
    """Loads YAML skills based on host_type + page_type.
    Follows Claude Code's progressive disclosure:
    - Metadata always loaded (name + description)
    - Full skill loaded only when page matches
    """

    def load_skills(self, host_type: str, page_type: str) -> list[ContextSkill]:
        """Returns skills matching the current context."""
        # 1. Look for exact match: {host_type}/{page_type}.skill.yaml
        # 2. Fall back to generic/{page_type}.skill.yaml
        # 3. Fall back to {host_type}/default.skill.yaml
        # 4. Fall back to generic/default.skill.yaml
```

---

## 7. Graph-Level Context Injection

### The Critical Fix

Page context MUST be injected at the **graph level**, before any agent runs.
This ensures ALL agents (RAG, Tutor, Memory, Direct, Synthesizer) automatically
receive page context without each agent needing to implement it.

```python
# app/engine/multi_agent/graph.py — in _build_prompt() or supervisor

def _inject_host_context(state: AgentState) -> str:
    """Graph-level host context injection.
    Called ONCE, result stored in state['host_context_prompt'].
    ALL agents include this in their system prompt."""
    ctx = state.get("context", {})
    host_ctx = ctx.get("host_context")  # HostContext object

    if not host_ctx:
        return ""

    adapter = get_host_adapter(host_ctx.host_type)
    return adapter.format_context_for_prompt(host_ctx)
```

### Where it gets injected

Instead of each agent calling `format_page_context_for_prompt()`:

```
BEFORE (Sprint 221 — fragile):
  graph.py/direct_agent: includes page_context ✅
  tutor_node.py: includes page_context ✅
  memory_agent.py: MISSING page_context ❌
  rag_node.py: MISSING page_context ❌

AFTER (Sprint 222 — robust):
  Graph entry point: injects host_context_prompt into state
  ALL agents: read state["host_context_prompt"] and include it
  → No agent can "forget" to include context
```

---

## 8. Frontend Changes (Wiii Embed)

### 8.1 Replace page-context-store with host-context-store

The current `page-context-store.ts` is LMS-specific. Replace with generic:

```typescript
// stores/host-context-store.ts
interface HostContextState {
  hostType: string | null;
  hostName: string | null;
  capabilities: HostCapabilities | null;
  currentContext: HostContext | null;
  pendingActions: Map<string, PendingAction>;

  // Actions
  setCapabilities: (caps: HostCapabilities) => void;
  updateContext: (ctx: HostContext) => void;
  requestAction: (action: string, params: any) => Promise<ActionResult>;
  requestEnrichment: (type: string) => Promise<EnrichmentResult>;
}
```

### 8.2 EmbedApp PostMessage Handler

```typescript
// Unified handler for all wiii: messages
const handler = (event: MessageEvent) => {
  const msgType = event.data?.type;
  if (!msgType?.startsWith('wiii:')) return;

  switch (msgType) {
    case 'wiii:capabilities':
      hostContextStore.setCapabilities(event.data.payload);
      break;
    case 'wiii:context':
      hostContextStore.updateContext(event.data.payload);
      break;
    case 'wiii:action-response':
      hostContextStore.resolveAction(event.data.id, event.data.result);
      break;
    case 'wiii:enrich-response':
      hostContextStore.resolveEnrichment(event.data.id, event.data.payload);
      break;
  }
};
```

### 8.3 Host Action Tools (Frontend → Backend Bridge)

When AI calls `tool_navigate(target="/courses/create")`:
1. Backend returns tool result as a "pending action" event in SSE stream
2. Frontend receives the event, sends PostMessage to host
3. Host executes the navigation
4. Host confirms via `wiii:action-response`
5. Frontend sends confirmation back to backend (or next chat message)

---

## 9. Backend Changes

### 9.1 New Package: `app/engine/context/`

| File | Purpose |
|------|---------|
| `host_context.py` | Pydantic models (HostContext, HostCapabilities) |
| `host_context_store.py` | In-memory per-session context (with LRU) |
| `host_adapter_registry.py` | Singleton registry of host adapters |
| `adapters/base.py` | HostAdapter ABC |
| `adapters/lms.py` | LMS adapter (inherits Sprint 221 logic) |
| `adapters/generic.py` | Fallback adapter |
| `prompt_assembler.py` | XML-tagged context assembly |
| `skill_loader.py` | YAML skill loading per host+page |
| `action_bridge.py` | Tool registration for host actions |

### 9.2 Integration Points

1. **ChatRequest.user_context** → extended with `host_context: HostContext`
2. **InputProcessor.build_context()** → extracts host_context
3. **Graph entry point** → calls `_inject_host_context()` → state["host_context_prompt"]
4. **ALL agents** → include `state["host_context_prompt"]` in system prompt
5. **Tool registration** → host-declared tools registered dynamically
6. **SSE events** → new event type `host_action` for bidirectional actions

---

## 10. Migration from Sprint 221

### What stays:
- PostMessage transport (iframe bridge)
- EmbedApp message handler structure
- Backend `format_page_context_for_prompt()` (moves into LMS adapter)
- Frontend `useSSEStream` context merge

### What changes:
- `page-context-store.ts` → `host-context-store.ts` (generic)
- `PageContext` schema → `HostContext.page` (generic)
- Per-agent injection → graph-level injection
- LMS-specific fields → `page.metadata` (host-specific)
- Read-only → bidirectional (action support)

### Backward compatibility:
- Old `wiii:page-context` messages still accepted (mapped to `wiii:context`)
- Old `PageContext` schema still parsed (wrapped in HostContext)
- Feature-gated: `enable_host_context=False` (new), falls back to Sprint 221

---

## 11. Feature Gates

```python
# app/core/config.py
enable_host_context: bool = False        # Master gate for v2
enable_host_actions: bool = False        # Bidirectional actions
enable_host_skills: bool = False         # Dynamic YAML skill loading
enable_host_enrichment: bool = False     # Content enrichment requests
```

---

## 12. Testing Strategy

### Unit Tests
- HostContext schema validation (generic + per-host-type)
- Host adapters (LMS, Generic) — prompt formatting, tool selection
- Skill loader — YAML parsing, priority resolution, fallback chain
- Action bridge — request/response matching, timeout handling
- Graph-level injection — all agents receive context

### Integration Tests
- PostMessage → HostContextStore → ChatRequest → prompt injection
- Action request → PostMessage → host response → tool result
- Enrichment request → host response → context update
- MCP compatibility — same schema via MCP transport

### E2E Tests
- LMS: navigate to lesson → ask about content → AI references page
- LMS: ask to create course → action request → host creates → confirmation
- Generic: unknown host type → fallback adapter → basic context
