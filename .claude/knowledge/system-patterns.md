# System Patterns - Wiii

**Last Updated:** 2026-02-09 (Sprint 24)

---

## Architecture Patterns

### 1. Clean Architecture Layers

```
API (app/api/) → Services (app/services/) → Engine (app/engine/) → Repositories (app/repositories/)
```

- **API Layer**: HTTP handling, request validation, response formatting
- **Service Layer**: Business logic orchestration, cross-cutting concerns
- **Engine Layer**: AI/ML logic, agents, RAG, memory
- **Repository Layer**: Data access, external API calls

### 2. Dependency Injection

All services receive dependencies via constructor:

```python
class ChatOrchestrator:
    def __init__(
        self,
        rag_agent: RAGAgent,
        semantic_memory: SemanticMemory,
        # ...
    ):
        self._rag_agent = rag_agent
        self._semantic_memory = semantic_memory
```

### 3. Singleton Pattern (LLM Pool)

LLM instances are shared via singleton pool to reduce memory:

```python
from app.engine.llm_pool import get_llm_deep, get_llm_moderate, get_llm_light
```

---

## Agent Patterns

### 4. Supervisor Pattern (LangGraph)

```python
# app/engine/multi_agent/supervisor.py
# Routes queries to specialized agents based on intent
Supervisor → [RAG | Tutor | Memory | Direct] → Grader → Synthesizer
```

### 5. ReAct Pattern (Unified Agent)

```python
# app/engine/unified_agent.py
# Reason + Act loop with tool binding
while not done and iterations < max_iterations:
    thought = llm.think(context)
    action = llm.select_tool(thought)
    result = execute_tool(action)
    context.update(result)
```

### 6. Corrective RAG (Self-Correction)

```python
# app/engine/agentic_rag/corrective_rag.py
retrieve → grade → [if low: rewrite query → retrieve again] → generate → verify
```

---

## Search Patterns

### 7. Hybrid Search (Dense + Sparse + RRF)

```python
# app/services/hybrid_search_service.py
dense_results = pgvector_search(query_embedding)
sparse_results = tsvector_search(query_text)
final_results = rrf_rerank(dense_results, sparse_results)
```

### 8. Tiered Grading (Early Exit)

```python
# app/engine/agentic_rag/retrieval_grader.py
Tier 1: Hybrid pre-filter (instant)
Tier 2: MiniJudge LLM (3-4s) → if ≥2 relevant: EARLY EXIT
Tier 3: Full LLM batch (19s)
```

---

## Memory Patterns

### 9. Semantic Memory (Cross-Session)

```python
# app/engine/semantic_memory/core.py
# Store and retrieve user facts using vector similarity
facts = await memory.get_user_facts(user_id)
await memory.save_fact(user_id, key="name", value="Minh")
```

### 10. Semantic Cache

```python
# app/cache/semantic_cache.py
# Cache responses by query similarity (threshold: 0.99)
cached = await cache.get_similar(query, threshold=0.99)
if cached:
    return cached.adapt_response()  # ThinkingAdapter
```

---

## API Patterns

### 11. Dual Authentication

```python
# app/core/security.py
# API Key OR JWT, with LMS headers
X-API-Key: key
X-User-ID: user-123
X-Session-ID: session-abc
X-Role: student|teacher|admin
```

### 12. Rate Limiting

```python
# app/core/rate_limit.py
@limiter.limit("30/minute")  # Chat endpoints
@limiter.limit("100/minute")  # General API
```

---

## Prompt Patterns

### 13. YAML Personas

```yaml
# app/prompts/agents/tutor.yaml
agent:
  id: "tutor_agent"
  backstory: "..."
style:
  tone: "Thân thiện"
  addressing:
    self: "mình"
```

### 14. Pronoun Adaptation

```python
# Detect user's pronoun style and adapt AI responses
# mình/cậu → AI uses mình
# em/anh → AI uses anh
# tôi/bạn → AI uses tôi (default)
```

---

## Error Handling Patterns

### 15. Graceful Degradation

```python
# Services continue if optional components unavailable
try:
    neo4j_result = await neo4j_repo.query(...)
except Neo4jException:
    logger.warning("Neo4j unavailable, continuing without graph context")
    neo4j_result = None
```

### 16. Structured Error Response

```python
# app/models/schemas.py
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict]
```

### 17. Scheduler Failure Tracking (Sprint 22)

```python
# app/repositories/scheduler_repository.py
# Tasks that fail 3+ times are auto-disabled
repo.mark_failed(task_id, "timeout")  # Increments failure_count
# get_due_tasks() filters: AND COALESCE(failure_count, 0) < 3
# After 3 failures: status changes from 'active' to 'failed'
```

### 18. Multi-Tenant Organization Pattern (Sprint 24)

```python
# app/core/org_context.py — ContextVar per-request org isolation
current_org_id: ContextVar[Optional[str]] = ContextVar('current_org_id', default=None)
current_org_allowed_domains: ContextVar[Optional[list[str]]] = ContextVar('current_org_allowed_domains', default=None)

# app/core/middleware.py — OrgContextMiddleware
# Extracts X-Organization-ID header → sets ContextVar → loads allowed_domains from DB
# Feature-gated: no-op when enable_multi_tenant=False
# Always resets ContextVar in finally block

# app/domains/router.py — Org-aware domain resolution
# 5-priority: explicit → session → keyword → default → org fallback
# allowed_domains filtering: reject domains outside org's allowed list

# app/core/thread_utils.py — Org-prefixed thread IDs
# build_thread_id("u1", "s1", org_id="lms") → "org_lms__user_u1__session_s1"
# build_thread_id("u1", "s1", org_id="default") → "user_u1__session_s1" (backward compat)
# parse_thread_id_full() → (org_id, user_id, session_id)
```

### 19. Processor Service Pattern (InputProcessor / OutputProcessor)

```python
# app/services/input_processor.py, output_processor.py
# Constructor DI with optional lazy deps, singleton getter + init
class InputProcessor:
    def __init__(self, guardian_agent=None, guardrails=None, ...):
        self._guardian_agent = guardian_agent  # Optional DI

    async def validate(self, request, session_id, create_blocked_response):
        # Guardian (LLM) → Guardrails (rules) → pass-through

    async def build_context(self, request, session_id, user_name=None):
        # asyncio.gather for parallel retrieval with return_exceptions=True
```
