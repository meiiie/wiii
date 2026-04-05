# Vision Local-First Post-Reset — 2026-04-03

## Summary

After machine reset, the local-first vision policy has been restored and persisted correctly.

The environment is now in a good operational state for Wiii vision:

- PostgreSQL is back up
- persisted runtime policy now includes capability-specific vision routing
- local smoke confirms general vision goes through `ollama / gemma3:4b`
- backend app health endpoint is alive again on port `8000`

## Persisted Policy Applied

Persisted in `admin_runtime_settings.llm_runtime`:

- `vision_provider = auto`
- `vision_describe_provider = ollama`
- `vision_describe_model = gemma3:4b`
- `vision_ocr_provider = auto`
- `vision_ocr_model = glm-ocr`
- `vision_grounded_provider = ollama`
- `vision_grounded_model = gemma3:4b`
- `vision_failover_chain = [ollama, google, openai, openrouter]`
- `vision_timeout_seconds = 60`

Also preserved / confirmed:

- `embedding_provider = auto`
- `embedding_failover_chain = [ollama, openai, google]`
- `embedding_model = embeddinggemma`
- `embedding_dimensions = 768`

Artifact:

- `E:/Sach/Sua/AI_v1/.Codex/reports/vision-local-policy-apply-2026-04-03.json`

## Live Verification

### Ollama models available

Relevant local models after restart:

- `gemma3:4b`
- `qwen2.5vl:3b`
- `embeddinggemma:latest`

### Runtime status

Local runtime currently resolves:

- `ollama + visual_describe -> gemma3:4b`
- `ollama + grounded_visual_answer -> gemma3:4b`

### Local smoke

Using:

- `docs/assets/screenshots/lms/lms-ai-chat-open.png`

Smoke result:

- success: `true`
- provider: `ollama`
- model: `gemma3:4b`

Representative output:

> Đây là giao diện của ứng dụng học tập "Cộng Học viên". Hiện tại, giao diện đang hiển thị thông báo "Chưa có khóa học đang học"...

This confirms the local-first path is not only configured, but actually executing.

## Infrastructure Recovery

Recovered services:

- `wiii-postgres` -> healthy on `5433`
- `wiii-app` -> health endpoint alive on `http://127.0.0.1:8000/api/v1/health/live`

Health response:

- `{"status":"alive"}`

## Operational Decision

For this workstation, the correct default remains:

- `visual_describe -> ollama / gemma3:4b`
- `grounded_visual_answer -> ollama / gemma3:4b`
- `ocr_extract -> specialist OCR lane (glm-ocr), not Gemma3`

This is based on measured local behavior, not on model branding.

## Notes

- `qwen2.5vl:3b` is installed and recognized, but is not the right default on this machine.
- It is better kept as a manual override / future benchmark candidate.
- OCR should stay separated as a specialist lane instead of collapsing the whole vision stack into one model.
