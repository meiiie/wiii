# Gotchas & Known Issues

**Last Updated:** 2026-02-09 (Sprint 24)

---

## Database

### 1. Neon Serverless Cold Start
**Issue:** First query after inactivity takes 3-5s (database wake-up)
**Location:** `app/core/database.py`
**Workaround:** Pool pre-ping enabled, 30s timeout configured

### 2. pgvector Index Performance
**Issue:** HNSW index needs tuning for large datasets
**Location:** `app/repositories/dense_search_repository.py`
**Note:** Current settings optimized for ~100K vectors

---

## LLM / AI

### 3. Gemini Rate Limits
**Issue:** Google API has per-minute quotas
**Location:** All LLM calls
**Workaround:** Use LLM pool (3 shared instances), implement retry with backoff

### 4. Token Budget Management
**Issue:** Large contexts can exceed token limits
**Location:** `app/engine/llm_factory.py`
**Note:** 3-tier system (DEEP: 8192, MODERATE: 4096, LIGHT: 1024)

### 5. Embedding Consistency
**Issue:** Must use same embedding model for indexing and querying
**Location:** `app/engine/gemini_embedding.py`
**Model:** `gemini-embedding-001` (768 dimensions)

---

## Async / Concurrency

### 6. Session Management
**Issue:** SQLAlchemy sessions are not thread-safe
**Location:** `app/core/database.py`
**Pattern:** Use `async with session_factory() as session:` for each operation

### 7. Neo4j Driver
**Issue:** Neo4j driver must be closed on shutdown
**Location:** `app/main.py` lifespan handler
**Note:** Failure to close can cause connection leaks

---

## Testing

### 8. Integration Tests Need Real Services
**Issue:** Tests marked `@pytest.mark.integration` require Neo4j, Google API
**Location:** `tests/integration/`
**Workaround:** Skip in CI without services, use mocks for unit tests

### 9. Async Test Fixtures
**Issue:** Must use `pytest-asyncio` with proper mode
**Location:** `pyproject.toml`
**Config:** `asyncio_mode = "auto"`

---

## Vietnamese Language

### 10. Pronoun Detection
**Issue:** Must detect user's pronoun style before building prompts
**Location:** `app/services/chat_service.py` → `detect_pronoun_style()`
**Styles:** mình/cậu, em/anh, tôi/bạn

### 11. Unicode Handling
**Issue:** Vietnamese text needs proper UTF-8 handling
**Location:** All text processing
**Note:** Always use `encoding='utf-8'` when reading/writing files

---

## Configuration

### 12. Feature Flags
**Issue:** Multiple flags control system behavior, can be confusing
**Location:** `app/core/config.py`
**Key flags:**
- `use_unified_agent` (False) vs `use_multi_agent` (True)
- `enable_corrective_rag` (True)
- `deep_reasoning_enabled` (True)

### 13. Environment Variables
**Issue:** Missing required vars cause silent failures
**Location:** `.env` / `app/core/config.py`
**Required:** `DATABASE_URL`, `GOOGLE_API_KEY`, `API_KEY`

---

## Performance

### 14. First Token Latency
**Issue:** Cold path takes ~62s, streaming first token ~20s
**Location:** RAG pipeline
**Optimization:** Semantic cache (2hr TTL), early exit grading

### 15. Memory Usage
**Issue:** Multiple LLM instances consume significant RAM
**Location:** `app/engine/llm_pool.py`
**Solution:** Singleton pool reduced from ~600MB to ~120MB (5x improvement)

---

## Security

### 16. API Key in Headers
**Issue:** API key sent in `X-API-Key` header
**Location:** `app/core/security.py`
**Note:** Always use HTTPS in production

### 17. Rate Limit Bypass
**Issue:** Rate limiting uses API key prefix or IP
**Location:** `app/core/rate_limit.py`
**Note:** Consider per-user limits for production

---

## Scheduler / Proactive Agent

### 18. Scheduler Failure Tracking (Sprint 22)
**Issue:** Scheduled tasks that timeout or error were retried infinitely (no failure tracking). Fixed in Sprint 22.
**Location:** `app/repositories/scheduler_repository.py`, `app/services/scheduled_task_executor.py`
**Fix:** `mark_failed()` increments `failure_count`; tasks with `failure_count >= 3` get `status='failed'` and are excluded from `get_due_tasks()`.
**DB Note:** Columns `failure_count` and `last_error` must exist on `scheduled_tasks` table (add via migration if needed).

### 19. Thread Upsert Silent Failures (Sprint 22)
**Issue:** `graph.py` logged thread upsert errors at `DEBUG` level — thread index could silently fall out of sync with LangGraph checkpointer.
**Location:** `app/engine/multi_agent/graph.py:701`
**Fix:** Changed to `logger.warning` with thread_id included for debugging.

---

## Testing Patterns

### 20. Lazy Import Patching
**Issue:** Many modules use lazy imports inside function bodies (e.g., `GuardianAgent`, `ValidationStatus`, `get_thinking_processor`). Patching at the consuming module fails with `AttributeError`.
**Pattern:** Always patch at the SOURCE module: `app.engine.guardian_agent.GuardianAgent`, not `app.services.input_processor.GuardianAgent`.
**Affected:** InputProcessor tests, OutputProcessor tests, all provider tests.

---

## Multi-Tenant / Multi-Organization (Sprint 24)

### 21. OrgContextMiddleware Lazy Import Patching
**Issue:** `OrgContextMiddleware.dispatch()` uses `from app.core.config import settings` (lazy import inside function body). Patching `app.core.middleware.settings` fails with `AttributeError`.
**Fix:** Patch at `app.core.config.settings` instead.
**Also:** `get_organization_repository` is lazy-imported — patch at `app.repositories.organization_repository.get_organization_repository`, NOT at `app.core.middleware.get_organization_repository`.

### 22. DomainRouter Lazy Settings Import
**Issue:** `router.py:resolve()` uses `from app.core.config import settings` inside the function body.
**Fix:** Patch at `app.core.config.settings` not `app.domains.router.settings`.

### 23. Organization "default" Cannot Be Deleted
**Issue:** `DELETE /api/v1/organizations/default` returns 400 — by design, the "default" org is protected.
**Location:** `app/api/v1/organizations.py:delete_organization()`

### 24. Thread ID Backward Compatibility
**Issue:** Old format `user_{uid}__session_{sid}` must still parse correctly alongside new org-prefixed format `org_{org}__user_{uid}__session_{sid}`.
**Location:** `app/core/thread_utils.py`
**Note:** `org_id="default"` produces legacy format (no prefix) for backward compat.

### 25. Empty allowed_domains Edge Case
**Issue:** When `allowed_domains=[]` (empty list, not None), no domain is allowed → falls to absolute fallback (`settings.default_domain`).
**Location:** `app/domains/router.py:resolve()`
**Note:** `None` means no filtering (all domains allowed), `[]` means nothing allowed.
