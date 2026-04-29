# Scripts

## Local Demo Smoke

Use this before a localhost demo. It verifies the dev-login JWT path, admin/org
permissions, runtime provider surface, sync chat, SSE V3 answer/metadata/done,
SSE first-event latency, SSE first-answer latency, and the local frontend.

```bash
python scripts/local_demo_smoke.py
```

Pinned NVIDIA demo gate:

```bash
python scripts/local_demo_smoke.py ^
  --provider nvidia ^
  --model deepseek-ai/deepseek-v4-flash ^
  --expect-provider nvidia ^
  --expect-model deepseek-ai/deepseek-v4-flash
```

For infrastructure-only checks while isolating provider failures:

```bash
python scripts/local_demo_smoke.py --skip-chat --skip-stream
```

If a model is intentionally slow during investigation, relax the SSE budget
explicitly instead of hiding the problem:

```bash
python scripts/local_demo_smoke.py --max-first-answer-seconds 75
```

Scripts cho development, testing và data ingestion.

---

## 🧪 Testing Scripts

### Main Test Scripts

| Script | Purpose |
|--------|---------|
| `test_streaming_v3.py` | **MAIN** - V3 streaming test (V1 vs V3 comparison) |
| `test_production_api.py` | Full API test suite |
| `test_chatbot_e2e.py` | End-to-end chatbot tests |
| `test_gemini_api_key.py` | Gemini API key validation (text, stream, JSON, embeddings, multimodal, burst) |

### Quick Test Commands

```bash
# Test V3 streaming (recommended)
python scripts/test_streaming_v3.py

# Test with routing validation
python scripts/test_streaming_v3.py --routing

# Full production API tests  
python scripts/test_production_api.py

# Gemini API key validation (balanced)
python scripts/test_gemini_api_key.py --mode full

# Minimal smoke check
python scripts/test_gemini_api_key.py --mode smoke --skip-multimodal

# Mixed workload: text + embeddings together
python scripts/test_gemini_api_key.py --mode full ^
  --mixed-text-models gemini-3.1-flash-lite-preview,gemini-3.1-pro-preview ^
  --mixed-thinking-levels medium,high
```

### Other Test Scripts

| Script | Purpose |
|--------|---------|
| `test_multimodal_api.py` | Multimodal ingestion tests |
| `test_streaming_api.py` | Basic SSE streaming tests |
| `test_hybrid_search.py` | Hybrid search tests |
| `test_memory_*.py` | Memory system tests |
| `test_reasoning_trace.py` | Reasoning trace validation |

---

## 📥 Ingestion Scripts

| Script | Purpose |
|--------|---------|
| `ingest_full_pdf.py` | Full PDF ingestion with bounding boxes |
| `ingest_local_full.py` | Local PDF ingestion |
| `reingest_multimodal.py` | Multimodal re-ingestion |
| `reingest_with_chunking.py` | Semantic chunking |
| `reingest_bounding_boxes.py` | Add bounding boxes to existing data |

```bash
# Ingest a PDF
python scripts/ingest_full_pdf.py --pdf data/document.pdf
```

---

## 🗃️ Database & Migration

| Script | Purpose |
|--------|---------|
| `run_migration.py` | Run Alembic migrations |
| `audit_database.py` | Database audit |

---

## 🛠️ Utilities

| Script | Purpose |
|--------|---------|
| `test_chat_ui.html` | Browser-based chat test UI |
| `test_proxy_server.py` | Proxy server for UI testing |

### Test UI Setup

```bash
# 1. Start proxy server (forwards to production)
python scripts/test_proxy_server.py

# 2. Start file server
cd scripts && python -m http.server 8080

# 3. Open browser: http://localhost:8080/test_chat_ui.html
```

---

## 📁 Subfolders

- `migrations/` - SQL migration files
- `data/` - Test data files
- `utils/` - Utility modules
