# Local Development Guide

This guide reflects the local runtime that was actually verified on
March 7, 2026.

## Current Recommended Local Stack

- backend: Docker container `wiii-app`
- database: Docker `postgres`
- object storage: Docker `minio`
- local model runtime: native host Ollama
- backend -> Ollama path: `http://host.docker.internal:11434`
- verified local model: `qwen3:4b-instruct-2507-q4_K_M`
- verified keep-alive: `30m`

Important:

- Docker Ollama still exists in `docker-compose.yml`, but it is now an opt-in
  profile, not the primary local path
- the currently verified fast local UI path used `USE_MULTI_AGENT=false`
- full multi-agent graph mode is a separate performance question
- `use_multi_agent` can now be inspected and changed through
  `GET/PATCH /api/v1/admin/llm-runtime` and the desktop Settings UI
- that runtime toggle changes the live backend process only; if you want the
  same mode after restart, keep `.env` or deployment config aligned

## Quick Start

### 1. Copy the environment file

```powershell
cd maritime-ai-service
Copy-Item .env.example .env
```

### 2. Choose your model strategy

Recommended product path:

- `LLM_PROVIDER=openrouter`
- `LLM_FAILOVER_CHAIN=["openrouter","ollama","google"]`

Current verified local-first fallback path:

```env
LLM_PROVIDER=ollama
LLM_FAILOVER_CHAIN=["ollama","google","openrouter"]
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M
OLLAMA_KEEP_ALIVE=30m
USE_MULTI_AGENT=false
```

If backend runs outside Docker, replace:

```env
OLLAMA_BASE_URL=http://localhost:11434
```

If you intentionally use the Docker Ollama profile, replace:

```env
OLLAMA_BASE_URL=http://ollama:11434
```

## 3. Start the local infrastructure

Start the standard local services:

```powershell
docker compose up -d postgres minio minio-init app
```

Optional services:

- `valkey` for task/cache flows
- `ollama` only if you want the containerized Ollama profile

Start those only when needed:

```powershell
docker compose --profile tasks up -d valkey
docker compose --profile ollama up -d ollama ollama-pull-qwen
```

## 4. Apply migrations

```powershell
docker compose exec app alembic upgrade head
```

Notes:

- local schema drift on March 7, 2026 involved `wiii_character_blocks` and
  `wiii_experiences`
- LangGraph checkpoint tables are now created automatically by the repaired
  checkpointer path, but keeping the database at migration head is still the
  correct baseline

## 5. Verify the backend

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/health/ollama
ollama ps
```

Expected local Ollama state for the verified path:

- `base_url` points to `http://host.docker.internal:11434`
- the active model is `qwen3:4b-instruct-2507-q4_K_M`
- after a request, `ollama ps` shows roughly `29-30 minutes` remaining

## 6. Verify the chat path

Sync API check:

```powershell
$headers = @{
  "X-API-Key" = "local-dev-key"
  "X-Session-ID" = "local-dev-sync"
  "X-User-ID" = "local-dev-user"
  "X-Role" = "student"
  "Content-Type" = "application/json"
}
$body = @{
  message = "Tra loi rat ngan de xac nhan sync path"
  user_id = "local-dev-user"
  role = "student"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/chat -Headers $headers -Body $body
```

## 7. Verify the real UI path

Start the frontend:

```powershell
cd ..\wiii-desktop
npm install
npm run dev -- --host 127.0.0.1 --port 1420
```

Then:

1. Open `http://127.0.0.1:1420`
2. Enter developer mode
3. Use API key `local-dev-key`
4. Send a short prompt

For the verified degraded local path, the backend logs should show:

- `[STREAM-V3] Multi-Agent disabled, using sync fallback path`
- `[FALLBACK] Multi-Agent unavailable, using local direct LLM`

## Local Runtime Modes

### Mode A: Recommended product mode

Use when evaluating product UX:

- `LLM_PROVIDER=openrouter`
- `LLM_FAILOVER_CHAIN=["openrouter","ollama","google"]`
- keep Ollama available as fallback/offline mode

### Mode B: Verified local degraded mode

Use when validating local/offline fallback:

- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- `OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M`
- `OLLAMA_KEEP_ALIVE=30m`
- `USE_MULTI_AGENT=false`

This mode is the one that produced the browser-verified
`~9.3s` first-assistant latency on March 7, 2026.

### Mode C: Docker Ollama profile

Use only if you intentionally want the model runtime inside Docker:

- start `docker compose --profile ollama up -d ollama ollama-pull-qwen`
- switch `OLLAMA_BASE_URL` to `http://ollama:11434`

Do not assume this matches the currently verified local setup.

### Mode D: Ollama Cloud direct API

Use when you want hosted Ollama inference without a local GPU runtime:

- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=https://ollama.com`
- `OLLAMA_API_KEY=...`
- choose a cloud-served model such as `gpt-oss:20b`

Important:

- Ollama's raw HTTP examples often show `https://ollama.com/api`
- in this repo, the `langchain-ollama` client expects the host root and appends
  `/api` internally
- the backend now normalizes either form, but `https://ollama.com` is the
  clearest value to store in runtime config and docs

## Troubleshooting

### `Graph processing error`

Check local database drift first, not Ollama wiring.

Known missing tables from the March 7, 2026 retest:

- `checkpoints`
- `checkpoint_blobs`
- `checkpoint_writes`
- `checkpoint_migrations`
- `wiii_character_blocks`
- `wiii_experiences`

Reference:

- `../../2026-03-07-ui-runtime-retest.md`
- `../../2026-03-07-local-llm-handoff.md`

### UI is much slower than sync chat

Check whether the runtime path matches the mode you think you are testing.

The earlier `60-67s` result happened because:

- sync chat respected `USE_MULTI_AGENT=false`
- streaming UI still forced the graph path

That parity bug has already been fixed.

### Ollama is reachable but feels slow

Check:

- model tag is explicit instruct, not generic `qwen3:4b`
- `OLLAMA_KEEP_ALIVE=30m`
- the model is still warm in `ollama ps`

## Files To Read First

- `../../2026-03-07-continuation-checkpoint.md`
- `../../2026-03-07-local-llm-handoff.md`
- `../../2026-03-07-ui-runtime-retest.md`
- `../../2026-03-07-model-strategy-recommendation.md`
- `../../2026-03-07-ollama-rollout-checklist.md`

## Current Bottom Line

The local host-native Ollama path is working.

The repo should now be treated as:

- host-native Ollama is the default local path
- Docker Ollama is opt-in
- OpenRouter remains the safer primary path for user-facing latency
