# Background / Session Workflow Hardening

Date: 2026-03-23  
Scope: `course_generation` durable workflow slice for production real data

## Executive Summary

Wiii's memory/session foundation was already in a healthier place than the long-running workflow layer. The weak spot for production real data was `course_generation`: jobs could survive restart, but large documents could still fail early on provider context limits, and long outline calls looked "stuck" because heartbeat only moved when a step finished.

This hardening round closes that gap in three layers:

- durable lifecycle + cancel/resume/recovery
- provider-aware source preparation before outline generation
- periodic heartbeat while long LLM work is in flight

The result is not yet a full shared job platform for every workflow in Wiii, but `course_generation` is now much closer to a production-grade background/session pattern.

This direction matches major platform guidance as of March 23, 2026:

- Anthropic: long-running work should be streamed, batched, or sessionized rather than left inside one unbounded synchronous request.  
  Source: [Anthropic API errors](https://docs.anthropic.com/en/api/errors)
- OpenAI: background mode is the safer pattern for long-running reasoning and generation tasks.  
  Source: [OpenAI Background mode](https://platform.openai.com/docs/guides/background)
- LangGraph: persistence/checkpointing is the correct backbone for resumable graph workflows.  
  Source: [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

## What Changed

### 1. Durable lifecycle metadata

Migration added to `course_generation_jobs`:

- `session_id`
- `thread_id`
- `progress_percent`
- `status_message`
- `started_at`
- `heartbeat_at`
- `completed_at`
- `cancel_requested`
- `cancelled_at`

File:
- [045_add_course_generation_lifecycle_fields.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/alembic/versions/045_add_course_generation_lifecycle_fields.py)

### 2. Repository lifecycle operations

`CourseGenerationRepository` now supports:

- persisted progress updates
- cancel request flagging
- cancel flag clearing for resume
- recent-job listing
- recovery query filtering that skips cancel-requested jobs

File:
- [course_generation_repository.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/course_generation_repository.py)

### 3. API lifecycle control

`/course-generation` now supports:

- `GET /course-generation`
- `GET /course-generation/{generation_id}`
- `POST /course-generation/{generation_id}/cancel`
- `POST /course-generation/{generation_id}/resume`

Status payloads now expose:

- progress
- status message
- cancel flag
- session/thread correlation
- heartbeat/start/completion/cancel timestamps

File:
- [course_generation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)

### 4. Cooperative cancellation and safer resume

The background workers now:

- check DB cancellation state before expensive work
- cancel local active tasks when possible
- persist `CANCELLED` instead of silently dying
- keep outline source files until outline success, so pre-outline failures/cancels can resume
- resume expand only for pending chapters, not chapters already completed
- preserve `expand_request` after completion to support later operational replay paths

### 5. Provider-aware outline source preparation

Large converted markdown is now compacted before the outline prompt is built.

New behavior:

- estimate source token size conservatively
- derive a safe source budget from the active provider route and immediate fallback
- keep the full markdown only when it already fits
- otherwise render a `chunk_compact` prepared document map
- fall back to a tighter `heading_index` view when budgets are extremely small

This means failover to a smaller practical context window no longer reuses the full raw document blindly.

Files:
- [course_generation_source_preparation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/workflows/course_generation_source_preparation.py)
- [course_generation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/workflows/course_generation.py)
- [outline.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/course_generation/outline.py)

### 6. Heartbeat while long LLM work is running

The outline phase now starts a periodic heartbeat loop while waiting on the long background structured call, and chapter expand waves also refresh heartbeat while parallel expansion is in flight.

This prevents the operational view from looking dead simply because the model is still working.

Files:
- [course_generation.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)

## Verification

Focused verification completed:

- `py_compile` on touched backend files: pass
- `pytest tests/unit/test_course_generation_source_preparation.py -q -p no:capture`: `4 passed`
- `pytest tests/unit/test_course_generation_flow.py -q -p no:capture`: `21 passed`

Previously green hardening suites still remain relevant:

- `pytest tests/unit/test_structured_invoke_service.py -q -p no:capture`: `5 passed`
- `pytest tests/unit/test_llm_runtime_policy_service.py tests/unit/test_admin_llm_runtime.py tests/unit/test_llm_failover.py -q -p no:capture`: `33 passed`

Live rollout verification completed:

- Docker Desktop started successfully
- `docker compose up -d` in `maritime-ai-service`: app + postgres + minio healthy
- `GET /health`: `200`, database connected
- `alembic current`: `041`
- `alembic upgrade head`: success
- `alembic current` after upgrade: `045 (head)`

## Live Smoke Findings

### 1. Medium PDF smoke no longer dies on prompt-length overflow

`VanBanGoc_95.2015.QH13.P1.pdf` produced:

- raw markdown: `122,305 chars`
- estimated raw tokens: `30,576`
- prepared mode: `chunk_compact`
- prepared tokens: `399`
- token budget used: `6,000`

Live logs confirmed:

- source preparation ran before outline
- outline started from the compacted document map, not raw markdown
- no `Prompt exceeds max length` failure was emitted for this run

### 2. Very large PDF smoke also compacted successfully

`building-microservices.pdf` produced:

- raw markdown: `1,385,668 chars`
- estimated raw tokens: `346,417`
- prepared mode: `chunk_compact`
- prepared tokens: `880`
- token budget used: `6,000`

Live logs confirmed:

- the source was compacted before outline
- outline started with a prepared source around `3,521 chars`
- the job did not fail immediately on provider prompt length

### 3. Heartbeat now moves during long outline generation

For both medium and very large PDF smoke runs:

- `progress_percent` stayed at `25` while outline was still running
- `heartbeat_at` refreshed roughly every `15s`
- status eventually shifted to the friendlier compact-source message:
  - `Dang tao outline tu ban do tai lieu da co dong`

This proves the operational view no longer looks frozen while waiting on a long provider call.

### 4. Cancel path still works end-to-end

Live cancel verification succeeded:

- `POST /course-generation/{id}/cancel` returned `200`
- in-flight outline jobs transitioned to `CANCELLED`
- `cancel_requested=true` and `cancelled_at` persisted

### 5. Remaining runtime limitation is provider speed/quota, not source size

In the smoke window, outline generation for these documents still did not always reach a terminal state quickly. The limiting factor is now provider runtime behavior:

- Google quota/rate pressure
- slower fallback outline generation when route degrades

This is a materially better failure mode than the earlier `Prompt exceeds max length` crash.

## Production Verdict

For the `course_generation` slice specifically:

- merge: `YES`
- deploy: `YES`, with provider/runtime guardrails

What is production-ready now:

- durable lifecycle persistence
- cancel / resume / recovery mechanics
- session/thread correlation
- provider-aware source compaction before outline
- periodic heartbeat during long background LLM calls
- structured invoke degradation path remains resilient under failover

What is still not fully green:

- very slow outline completion under degraded provider conditions
- no dedicated `OUTLINING` phase label yet; operationally the job is still visible as `CONVERTING` while the outline call is running
- no shared job framework yet for all other long workflows

## Remaining Gaps

This is not yet a full platform-wide durable job engine.

Still deferred:

- generic background job framework shared by multiple workflows
- live push/stream of job progress to desktop UI
- explicit artifact retention / cleanup policy for cancelled pre-outline temp files
- durable queue handoff across multiple workers/processes beyond current recovery model
- deeper integration between long-running job progress and Wiii memory/teaching context
- provider-aware source budgets for later phases beyond outline

## Recommended Next Step

Use this hardened `course_generation` flow as the template for:

1. Code Studio long-running generation
2. artifact-build workflows
3. crawl / ingestion tasks that still rely on fire-and-forget execution

Immediate next engineering step for real production data:

1. add a distinct `OUTLINING` phase for clearer operator visibility
2. reuse the same source-budget idea for later long-context generation phases
3. surface background job progress and cancellation more directly in desktop UI

The right path is still to grow this into a shared durable workflow pattern, not to reintroduce unbounded request-time execution.
