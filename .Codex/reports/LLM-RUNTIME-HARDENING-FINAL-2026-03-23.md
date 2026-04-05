# LLM Runtime Hardening Final Report

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`

## Scope Completed

- Applied database migrations through revision `041`.
- Hardened migration `040` so partially-created `course_generation_jobs` tables can be reconciled safely.
- Enabled durable admin runtime audit persistence via `admin_runtime_settings`.
- Installed `langchain-ollama` in the project `.venv`.
- Aligned the active `.venv` AI runtime stack closer to repo expectations:
  - `langchain==1.2.11`
  - `langchain-core==1.2.18`
  - `langgraph==1.1.0`
  - `langchain-google-genai==4.2.1`
  - `google-genai==1.66.0`
  - `langchain-ollama==0.3.10`
- Removed legacy `google-generativeai` from `.venv` and updated local-dev dependency checks to use `google-genai`.
- Re-ran focused backend and frontend verification.
- Re-ran full live capability discovery/probe and persisted the resulting audit snapshot.

## Database State

### Alembic

- Current revision: `041 (head)`

### Verified Tables

- `admin_runtime_settings`: present
- `course_generation_jobs`: present

### Verified `course_generation_jobs` schema

The table now includes the previously-missing `expand_request` column, so the live schema matches the current migration intent.

## Verification

### Backend

- `pytest tests/unit/test_llm_runtime_audit_service.py tests/unit/test_admin_llm_runtime.py tests/unit/test_llm_runtime_metadata.py tests/unit/test_model_catalog_service.py tests/unit/test_llm_providers.py -q -p no:capture`
- Result: `73 passed`

### Frontend

- `npx tsc --noEmit --pretty false`
- Result: pass

## Live Runtime Audit Result

Audit persistence is now working against the database.

- `audit_persisted = true`
- `degraded_providers = ["google", "ollama"]`

### Provider Verdicts

#### Google Gemini

- Selected model: `gemini-3.1-flash-lite-preview`
- Runtime catalog source: `mixed`
- Status: degraded
- Probe result:
  - tool calling: probe failed (`timeout`)
  - structured output: probe failed (`timeout`)
  - streaming: probe failed (`429 quota_or_rate_limited`)

Interpretation:
- Google remains the intended default runtime.
- The current environment/API key is quota-limited, so probe reliability is constrained by billing/quota rather than code path correctness.

#### Zhipu GLM

- Selected model: `glm-5`
- Runtime catalog source: `runtime`
- Status: healthy
- Probe result:
  - tool calling: supported
  - structured output: supported
  - streaming: supported

Interpretation:
- Zhipu is now a healthy fallback/runtime option in this environment.
- Provider-specific JSON-mode probing fixed the previous false-negative structured-output verdict.

#### Ollama

- Selected model: `qwen3:4b-instruct-2507-q4_K_M`
- Status: degraded
- Probe result:
  - dependency issue: resolved (`langchain-ollama` installed)
  - availability now reflects real host reachability
  - runtime discovery/probe currently fails because `http://host.docker.internal:11434` is unreachable from the backend runtime

Interpretation:
- The environment is now code-ready for Ollama.
- Remaining issue is operational connectivity to the configured Ollama host, not Python dependency drift.

#### OpenAI

- Status: not configured
- Probe note: provider not configured

#### OpenRouter

- Status: not configured as the active shared OpenAI-compatible slot
- Probe note: shared slot currently targets `openai`, not `openrouter`

## Code Changes Of Note

- `alembic/versions/040_create_course_generation_jobs.py`
  - upgraded to idempotent/backfill-safe behavior
- `alembic/versions/041_create_admin_runtime_settings.py`
  - applied successfully to the live DB
- `app/services/llm_runtime_audit_service.py`
  - durable audit path now active
  - partial probe failures produce clearer capability state
  - OpenAI-compatible providers now use provider-specific JSON-mode structured-output probes
- `app/api/v1/admin.py`
  - admin runtime audit now persists and surfaces operational truth
- `app/engine/llm_providers/ollama_provider.py`
  - provider availability now checks real host reachability with short-lived caching
- `app/engine/llm_runtime_metadata.py`
  - fixed provider/model resolution for `zhipu`
- `scripts/run_local_dev.py`
  - removed legacy `google.generativeai` dependency check
- `pyproject.toml`
  - now includes `langchain-ollama`

## Remaining Recommendations

1. Increase or stabilize Google quota/billing for the runtime API key, then re-run the live probe.
2. Verify the configured Ollama host is actually reachable from the backend runtime, then re-run the live probe.
3. Investigate the residual runtime warning from the Google probe path (`google-genai` / `aiohttp`: `coroutine 'ClientResponse.json' was never awaited`), even though it does not currently block audit persistence or provider verdicts.
