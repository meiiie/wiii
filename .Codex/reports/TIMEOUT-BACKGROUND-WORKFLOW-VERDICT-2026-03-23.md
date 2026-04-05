# Timeout Policy + Background Workflow Verdict

Date: 2026-03-23
Owner: Codex LEADER
Scope: Admin-managed timeout policy, provider-aware runtime timeouts, background/session workflow direction for Wiii

## What Was Implemented

- Added persisted timeout policy controls to the backend runtime policy path.
  - Global profiles now cover:
    - `light`
    - `moderate`
    - `deep`
    - `structured`
    - `background`
    - `stream_keepalive_interval`
    - `stream_idle_timeout`
  - Provider-specific overrides now support:
    - `google`
    - `zhipu`
    - `openai`
    - `openrouter`
    - `ollama`
- Added admin/runtime API schema support so timeout policy is visible and editable through `/api/v1/admin/llm-runtime`.
- Added shared desktop admin/settings UI controls for:
  - global timeout profiles
  - provider-specific timeout overrides
- Updated runtime resolution so provider override wins over global tier timeout when a request resolves to that provider.

## Files Changed

- Backend:
  - `maritime-ai-service/app/engine/llm_timeout_policy.py`
  - `maritime-ai-service/app/engine/llm_pool.py`
  - `maritime-ai-service/app/core/config/_settings.py`
  - `maritime-ai-service/app/core/config/llm.py`
  - `maritime-ai-service/app/services/llm_runtime_policy_service.py`
  - `maritime-ai-service/app/api/v1/admin.py`
- Frontend:
  - `wiii-desktop/src/api/types.ts`
  - `wiii-desktop/src/components/runtime/LlmRuntimePolicyEditor.tsx`
- Tests:
  - `maritime-ai-service/tests/unit/test_llm_runtime_policy_service.py`
  - `maritime-ai-service/tests/unit/test_admin_llm_runtime.py`
  - `maritime-ai-service/tests/unit/test_llm_failover.py`
  - `wiii-desktop/src/__tests__/admin-runtime-tab.test.tsx`

## Verification

- Backend focused tests: `33 passed`
- Frontend typecheck: pass
- Frontend admin runtime tests: `5 passed`

## External Guidance (Official Sources)

### Anthropic / Claude

- Anthropic’s error guidance says long requests should use streaming or message batches rather than a single long blocking request:
  - [Anthropic API errors](https://docs.anthropic.com/en/api/errors)
- Anthropic’s build guidance consistently favors streamed, stateful, tool-using workflows over giant one-shot calls:
  - [Claude prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### OpenAI

- OpenAI’s current platform guidance for long-running reasoning work is to use background processing patterns rather than forcing one synchronous response path:
  - [Background mode guide](https://platform.openai.com/docs/guides/background)

### LangGraph / LangChain

- LangGraph’s official model for long-running agents is durable execution with thread identity, persistence, checkpoints, and memory/store:
  - [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  - [LangGraph add memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
  - [LangChain long-term memory](https://docs.langchain.com/oss/python/deepagents/long-term-memory)

## Wiii Assessment

### 1. Memory / Context

This part is already relatively strong.

- `maritime-ai-service/app/services/input_processor.py`
  - Builds semantic context, history, summary, host/page context, and user facts into one request context.
- `maritime-ai-service/app/services/session_manager.py`
  - Maintains session/thread continuity and per-session interaction state.
- `maritime-ai-service/app/services/background_tasks.py`
  - Persists post-response memory work such as semantic interaction storage and summarization.
- `maritime-ai-service/app/engine/context_manager.py`
  - Already provides token budgeting and context compaction.
- `maritime-ai-service/app/engine/multi_agent/checkpointer.py`
  - Gives Wiii a better-than-average base for thread-scoped graph persistence.

Verdict:
- Memory and context are not the weakest part anymore.
- They are good enough to support a more durable long-running workflow layer.

### 2. Background / Long-Running Workflows

This is the area that still needs the next architectural step.

Current state:
- Wiii has background task runners after chat response.
- Wiii has session/thread identity.
- Wiii has graph checkpointing in important places.

What is still missing:
- a first-class durable job/session orchestration model for very long tasks
- explicit job lifecycle states such as queued/running/paused/completed/failed/cancelled
- resumable background tasks with progress replay
- artifact/job persistence that survives worker restarts cleanly

Verdict:
- Wiii is ready for provider-aware timeout control now.
- Wiii is **not yet** a full durable background execution platform in the LangGraph/Anthropic sense.

## Recommended Production Policy

### Keep

- First-response timeouts for interactive requests
- Stream keepalive
- Optional stream idle timeout
- Provider-specific timeout overrides

### Do Not Do

- Do not remove timeouts globally from sync `/chat`
- Do not let very long code/artifact/course workflows depend on one long synchronous request

### Use Instead

- Interactive chat:
  - `light`, `moderate`, `deep`
- Structured routing / planners / validators:
  - `structured`
- Long-running workflows:
  - `background`
  - plus durable job/session execution in a later phase

## Practical Next Step

The correct next phase is not “raise timeout again and again”.

It is:

1. Define a durable background job model for Code Studio / course generation / heavy synthesis.
2. Bind jobs to `thread_id` / session identity and checkpointer state.
3. Stream progress and heartbeat while persisting intermediate artifacts.
4. Allow cancel/resume/retry from admin or user UI.

## Merge Verdict

- Timeout policy uplift: `YES`
- Admin/runtime UI support: `YES`
- Production readiness for interactive runtime policy: `YES`
- Production readiness for truly long-lived background workflows: `PARTIAL`

Short conclusion:

Wiii now has the right timeout policy surface for production operations.
The next major architectural investment should be a durable background job/session layer, not a move toward infinite synchronous requests.
