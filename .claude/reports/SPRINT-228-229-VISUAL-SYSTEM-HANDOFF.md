# Sprint 228-229: Interactive Visual Widget System — Handoff Report
**Date:** 2026-03-14
**Author:** Claude Opus 4.6 (AI Lead)
**Status:** Backend DONE, Frontend rendering cần verify trên browser

---

## 1. Mục tiêu tổng quan

Xây dựng hệ thống **inline interactive visuals** cho Wiii — giống Claude Artifacts của Anthropic. AI tự động tạo biểu đồ, so sánh, mô phỏng, quiz... render trực tiếp trong chat dưới dạng iframe tương tác.

**Tham khảo:** https://claude.com/blog/claude-builds-visuals

---

## 2. Kiến trúc tổng thể

```
User hỏi "so sánh TCP và UDP"
         ↓
    Supervisor route → direct/code_studio agent
         ↓
    AI gọi tool_generate_rich_visual(type="comparison", spec_json=...)
         ↓
    Tool trả về ```widget\n<HTML+CSS+SVG>\n```
         ↓
    _inject_widget_blocks_from_tool_results() inject vào response
         ↓
    Frontend nhận response qua SSE streaming
         ↓
    MarkdownRenderer.splitWidgetBlocks() tách widget blocks TRƯỚC markdown parsing
         ↓
    InlineHtmlWidget render HTML trong sandboxed iframe (blob: URL)
         ↓
    User thấy visual tương tác inline trong chat
```

---

## 3. Các file đã tạo/sửa

### Backend (maritime-ai-service/)

| File | Thay đổi | Sprint |
|------|----------|--------|
| **`app/engine/tools/visual_tools.py`** | **MỚI** — 10 visual types, design system CSS, HTML builders | 229 |
| `app/engine/tools/chart_tools.py` | Có sẵn — Chart.js tool (Sprint 228b) | 228b |
| `app/engine/multi_agent/graph.py` | Thêm visual tools vào direct + code_studio agents, force tool, widget injection | 229d-i |
| `app/prompts/agents/tutor.yaml` | Visual section: mermaid → chart → rich_visual 3-tier | 229 |
| `app/prompts/agents/rag.yaml` | Tương tự tutor.yaml | 229 |
| `app/prompts/agents/direct.yaml` | Tương tự tutor.yaml | 229 |
| `app/prompts/agents/assistant.yaml` | Tương tự tutor.yaml | 229 |
| `app/prompts/prompt_loader.py` | Render 3-tier visual (chart + rich_visual + legacy widget) | 229 |
| `app/main.py` | Mount web SPA tại `/` (StaticFiles) | 228c |
| `Dockerfile.prod` | Copy dist-web + dist-embed | 228c |
| `scripts/deploy/.env.production.template` | Thêm OAUTH_ALLOWED_REDIRECT_ORIGINS | 228c |
| `tests/unit/test_visual_tools.py` | **MỚI** — 61 tests | 229 |
| `tests/unit/test_visual_prompt.py` | Cập nhật cho 3-tier visual | 229 |

### Frontend (wiii-desktop/)

| File | Thay đổi | Sprint |
|------|----------|--------|
| **`src/components/common/InlineHtmlWidget.tsx`** | **MỚI** (Sprint 228) — Sandboxed iframe renderer, CSP, resize | 228+229 |
| `src/components/common/MarkdownRenderer.tsx` | splitWidgetBlocks() pre-extract widget trước markdown | 229g |
| `src/lib/constants.ts` | DEFAULT_SERVER_URL = window.location.origin (fix 401) | 228c |

---

## 4. 10 Visual Types có sẵn

### Static (HTML+CSS+SVG — không cần JS)

| Type | Mô tả | Khi nào dùng |
|------|--------|-------------|
| `comparison` | So sánh 2 thứ side-by-side | "so sánh X và Y" |
| `process` | Quy trình từng bước + arrows | "quy trình...", "các bước..." |
| `matrix` | Heatmap/grid với hover | Ma trận, confusion matrix |
| `architecture` | Layers + components diagram | Kiến trúc hệ thống |
| `concept` | Central idea + branches | Bản đồ khái niệm |
| `infographic` | Stats + sections | Tổng hợp số liệu |

### Interactive (HTML+CSS+JS — có tương tác)

| Type | Mô tả | Khi nào dùng |
|------|--------|-------------|
| `simulation` | Canvas + requestAnimationFrame + sliders | Vật lý, toán, animation |
| `quiz` | Click chọn đáp án, tính điểm | Kiểm tra kiến thức |
| `interactive_table` | Sort, search, filter | Bảng dữ liệu |
| `react_app` | Full React 18 + Tailwind + Recharts | Dashboard phức tạp |

---

## 5. Cách tool hoạt động

### Backend: `tool_generate_rich_visual`

```python
# AI gọi tool với:
tool_generate_rich_visual(
    visual_type="comparison",
    spec_json='{"left": {"title": "TCP", "items": [...]}, "right": {"title": "UDP", "items": [...]}}',
    title="So sánh TCP và UDP"
)

# Tool trả về:
# ```widget
# <!DOCTYPE html>
# <html>...<CSS design system>...<HTML body>...</html>
# ```
```

### Frontend: Render flow

```
Response text: "```widget\n<html>...</html>\n```\nGiải thích thêm..."
         ↓
splitWidgetBlocks() → [
  { type: "widget", content: "<html>...</html>" },
  { type: "markdown", content: "Giải thích thêm..." }
]
         ↓
Widget → InlineHtmlWidget (sandboxed iframe)
Markdown → ReactMarkdown (normal rendering)
```

---

## 6. Cơ chế quan trọng

### 6.1 Widget Injection (backend)

**File:** `graph.py` → `_inject_widget_blocks_from_tool_results()`

**Vấn đề:** AI gọi tool nhưng không copy widget code block vào response.
**Fix:** Backend tự động extract ```widget blocks từ tool results và prepend vào AI response.

### 6.2 Force Tool (backend)

**File:** `graph.py` → `_direct_required_tool_names()` + `_collect_direct_tools()`

**Vấn đề:** AI không gọi visual tool vì `force_tools=False`.
**Fix:** Khi query chứa "so sánh", "compare", "visual", "diagram"... → force `tool_generate_rich_visual`.

### 6.3 Pre-extract Widget (frontend)

**File:** `MarkdownRenderer.tsx` → `splitWidgetBlocks()`

**Vấn đề:** rehype-sanitize mangle HTML bên trong ```widget code fence.
**Fix:** Extract widget blocks TRƯỚC khi đưa vào ReactMarkdown pipeline. Render trực tiếp qua InlineHtmlWidget.

### 6.4 CDN Whitelist (frontend)

**File:** `InlineHtmlWidget.tsx` → `ALLOWED_CDNS`

Iframe sandbox cho phép load scripts từ:
- `cdn.jsdelivr.net` — Chart.js, Recharts
- `cdnjs.cloudflare.com` — fallback CDN
- `unpkg.com` — React, ReactDOM, Babel
- `d3js.org` — D3.js
- `cdn.katex.org` — KaTeX math
- `cdn.tailwindcss.com` — Tailwind Play CDN

---

## 7. Deployment

### Web SPA

```bash
# Build frontend
cd wiii-desktop
npm run build:web    # → dist-web/

# Upload to server
tar -czf dist-web.tar.gz dist-web/
gcloud compute scp dist-web.tar.gz wiii-production:/tmp/ --zone=asia-southeast1-b
gcloud compute ssh wiii-production --zone=asia-southeast1-b --command="
  cd /opt/wiii
  sudo rm -rf wiii-desktop/dist-web
  sudo tar -xzf /tmp/dist-web.tar.gz -C wiii-desktop/
"
```

### Docker rebuild

```bash
gcloud compute ssh wiii-production --zone=asia-southeast1-b --command="
  cd /opt/wiii
  sudo docker build --no-cache -f maritime-ai-service/Dockerfile.prod -t wiii-app-local:latest .
  cd maritime-ai-service
  sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d --force-recreate app
"
```

### QUAN TRỌNG: Update Nginx container

Nginx serve static files từ **riêng** container của nó (`wiii-nginx`), KHÔNG phải từ app container. Sau khi build Docker mới, PHẢI copy dist-web vào Nginx:

```bash
gcloud compute ssh wiii-production --zone=asia-southeast1-b --command="
  cd /opt/wiii
  sudo docker cp wiii-desktop/dist-web/. wiii-nginx:/usr/share/nginx/html/
"
```

Không làm bước này → browser vẫn load bundle JS cũ.

---

## 8. Vấn đề còn tồn đọng (TODO cho team tiếp)

### 8.1 Streaming Widget Rendering (HIGH)

**Vấn đề:** Trong lúc SSE streaming, widget HTML đến từng chunk. `splitWidgetBlocks()` chỉ match khi fence đóng hoàn chỉnh. Kết quả: trong lúc streaming thấy raw code, sau khi xong mới render widget.

**Giải pháp đề xuất:**
- Option A: Backend emit widget as separate SSE event type (`widget` thay vì `answer_delta`)
- Option B: Frontend buffer answer chunks cho đến khi detect complete widget fence
- Option C: Chấp nhận UX hiện tại (code trong lúc streaming → widget sau khi xong)

### 8.2 Visual Quality (MEDIUM)

**Vấn đề:** Output HTML hiện tại là styled lists/text. Claude tạo custom SVG diagrams (matrices, flowcharts, animations).

**Giải pháp đề xuất:**
- Thêm SVG templates vào các visual builders (đặc biệt comparison + matrix)
- Thêm animations (CSS transitions, GSAP)
- Cải thiện design system (gradient, shadows, icons)

### 8.3 Nginx Static Files Workflow (MEDIUM)

**Vấn đề:** Phải manually copy dist-web vào Nginx container sau mỗi deploy. Dễ quên → serve bundle cũ.

**Giải pháp đề xuất:**
- Tạo Nginx Dockerfile riêng COPY dist-web vào image
- Hoặc dùng shared Docker volume giữa app và nginx containers
- Hoặc bỏ Nginx serve SPA, để FastAPI StaticFiles serve (đã có mount tại `/`)

### 8.4 React App Type Testing (LOW)

**Vấn đề:** `react_app` type chưa được test trên production. CDN load (React + Babel + Tailwind) nặng (~1.5MB).

**Giải pháp đề xuất:**
- Test với use case cụ thể (dashboard, interactive chart)
- Cân nhắc dùng Preact + htm thay React + Babel (nhẹ hơn 100x)
- Lazy load CDN libs

---

## 9. Test Commands

### Backend tests

```bash
cd maritime-ai-service
set PYTHONIOENCODING=utf-8
python -m pytest tests/unit/test_visual_tools.py tests/unit/test_visual_prompt.py -v -p no:capture
# Expected: 61 passed
```

### Frontend tests

```bash
cd wiii-desktop
npx vitest run src/__tests__/inline-html-widget.test.tsx
# Expected: 7 passed
```

### API test (production)

```bash
API_KEY="05060ef84eb077d93a1d3bae0fe2b37dab68c1b38687749491bd62ae82ae2dde"
curl -s -X POST "https://wiii.holilihu.online/api/v1/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-User-ID: test" \
  -H "X-Session-ID: test" \
  -H "X-Role: student" \
  -d '{"message": "so sanh TCP va UDP", "user_id": "test", "session_id": "test", "role": "student"}'

# Expected: response.data.answer chứa ```widget\n<!DOCTYPE html>...
# Expected: metadata.tools_used = [{"name": "tool_generate_rich_visual"}]
```

---

## 10. Commits (theo thứ tự)

| Commit | Message |
|--------|---------|
| `28dc391` | Sprint 228: InlineHtmlWidget + MarkdownRenderer widget routing |
| `24dee7b` | Sprint 228b: tool_generate_interactive_chart for Code Studio |
| `40ac7ae` | Sprint 228c: Web SPA deployment, fix 401 auth |
| `c36b635` | Sprint 229: Rich visual tool (6 types) + prompt 3-tier |
| `e54965b` | Sprint 229b: simulation, quiz, interactive_table |
| `3d35be6` | Sprint 229c: react_app with React 18 + Tailwind + Recharts |
| `7ccdb56` | Sprint 229d: Auto-inject widget blocks from tool results |
| `9b24e23` | Sprint 229e: Visual tools in direct agent |
| `37eeceb` | Sprint 229f: Fix Gemini list content handling |
| `67b8b4b` | Sprint 229g: Pre-extract widget blocks before markdown |
| `d48b66d` | Sprint 229h: Tolerant regex + max-height 900px |
| `8f3d8ee` | Sprint 229i: Force visual tool on comparison/visual queries |

---

## 11. Kiến trúc so sánh với Claude

| | Claude Artifacts | Wiii Widget System |
|---|---|---|
| Runtime | React 18 + Babel | React 18 + Babel (CDN) |
| Styling | Tailwind CSS | Tailwind Play CDN + Design System CSS |
| Charts | Recharts | Recharts + Chart.js |
| Sandbox | iframe (claudeusercontent.com) | iframe (blob: URL + CSP) |
| Communication | postMessage | postMessage (resize) |
| Rendering | Side panel + inline | Inline in chat |
| Trigger | AI decides automatically | Force tool on keyword signals |

---

## 12. Liên hệ & Tài liệu

- **Codebase:** https://github.com/meiiie/LMS_AI
- **Production:** https://wiii.holilihu.online/
- **GCP VM:** `wiii-production` (asia-southeast1-b, e2-medium)
- **Claude blog tham khảo:** https://claude.com/blog/claude-builds-visuals
- **Reverse engineering Claude Artifacts:** https://www.reidbarber.com/blog/reverse-engineering-claude-artifacts
