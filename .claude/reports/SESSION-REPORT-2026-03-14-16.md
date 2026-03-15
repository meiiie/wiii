# Session Report — 14-16 tháng 3, 2026
**Agent:** Claude Opus 4.6 (1M context)
**Tổng commits:** 51
**Sprints:** 228c, 229a-i, 230a-e, 231a-l, 232, V5

---

## 1. Web SPA Deployment (Sprint 228c)

**Vấn đề:** Web app không hoạt động — 401 auth errors, favicon sai, không responsive.
**Giải pháp:**
- `DEFAULT_SERVER_URL = window.location.origin` (fix 401)
- Mount web SPA tại `/` via FastAPI StaticFiles
- Dockerfile copy `dist-web` vào Docker image
- OAuth redirect whitelist thêm `https://wiii.holilihu.online`

**Files:** `constants.ts`, `main.py`, `Dockerfile.prod`, `.env.production.template`

---

## 2. Interactive Visual Widget System (Sprint 229a-i)

**Vấn đề:** AI không tạo được interactive visuals inline trong chat.
**Giải pháp:**
- **10 visual types**: comparison, process, matrix, architecture, concept, infographic, simulation, quiz, interactive_table, react_app
- **React runtime**: React 18 + Tailwind + Recharts trong sandboxed iframe
- **Auto-inject widget blocks**: Backend tự extract `widget` code từ tool results → inject vào AI response
- **Force visual tool**: Khi query có "so sánh", "compare" → bắt buộc gọi `tool_generate_rich_visual`
- **Pre-extract widget**: Frontend `splitWidgetBlocks()` tách widget HTML trước markdown parsing
- **CDN whitelist**: Chart.js, D3.js, KaTeX, Tailwind Play CDN, Recharts

**Files:** `visual_tools.py`, `graph.py`, `InlineHtmlWidget.tsx`, `MarkdownRenderer.tsx`, `InlineVisualFrame.tsx`, 4 YAML prompts

---

## 3. SEO & Branding (Sprint 230a-e)

**Vấn đề:** Không có SEO, favicon sai, không có OG image.
**Giải pháp:**
- Full meta tags: title, description, OG (7 tags), Twitter Card, JSON-LD (WebApplication schema)
- **Mascot kawaii** = logo chính thức Wiii AI (favicon, app icon, OG image)
- `robots.txt`, `sitemap.xml`, `manifest.webmanifest` (PWA)
- Nginx cache headers: favicon 1h, OG image 1h, index.html no-cache
- Favicon cache-busting `?v=2`

**Files:** `index.html`, `public/` (favicon, icons, robots, sitemap, manifest), `nginx.conf`

---

## 4. UX/UI Improvements (Sprint 231a-l)

### 4.1 Layout
- **Xóa TitleBar** trên web (+44px vertical space)
- **Xóa StatusBar** trên web (+32px vertical space)
- **Sidebar 260px** (match Claude/ChatGPT, was 288px)
- **Mobile responsive**: sidebar overlay + backdrop (<768px)
- **Welcome content** nâng lên optical center (`pt-[12vh]`)

### 4.2 Sidebar
- **Footer simplified**: 6 items → avatar click → dropdown menu (Claude pattern)
- **Sidebar close button** trong header
- **Icon rail** mở sidebar ở đầu rail (PanelLeft icon)
- **Mobile hamburger** menu button

### 4.3 Greeting
- Không còn "User" generic — filter names like "User", "Desktop User", "anonymous"

### 4.4 Login Screen
- **Google button**: shadow-md, rounded-2xl, h-48px, font-semibold
- **Email input**: h-44px, rounded-xl, focus ring
- **"Tiếp tục"**: rounded-2xl, font-semibold
- **Terms/Privacy**: Professional pages (terms.html, privacy.html) with header + footer
- **Optical center**: pt-[10vh]
- **Gradient background**

**Files:** `AppShell.tsx`, `TitleBar.tsx`, `StatusBar.tsx`, `Sidebar.tsx`, `ChatView.tsx`, `WelcomeScreen.tsx`, `LoginScreen.tsx`, `greeting.ts`, `globals.css`

---

## 5. Scaling Infrastructure (Sprint 232)

**Vấn đề:** Production chỉ chịu được ~30-50 concurrent users.
**Giải pháp (config sẵn, CHƯA triển khai):**
- Docker Compose: `APP_REPLICAS` env var, `least_conn` Nginx
- `GUNICORN_WORKERS=8`, `APP_REPLICAS=3` → 24 workers → ~1000 users
- VM upgrade path: e2-medium → e2-standard-4
- PgBouncer template sẵn

**Files:** `docker-compose.prod.yml`, `nginx.conf`, `.env.production.template`
**Guide:** `.claude/reports/SCALING-1000-USERS-GUIDE.md`

---

## 6. V5 Article-First Visual System

### 6.1 Structured Visuals
- `enable_structured_visuals=True` — activates `tool_generate_visual` (multi-figure payload)
- Figure planner: 1-3 figures tùy query complexity
- Pedagogical roles: problem → mechanism → conclusion

### 6.2 Seamless Figures (Claude Parity)
- **Zero figure chrome**: no bridge chip, no decorative lines, no card shadow/border
- **Transparent backgrounds**: all templates (architecture, concept, infographic, comparison)
- **Editorial shell**: `wiii-frame-shell` → border: none, bg: transparent, radius: 0
- **iframe**: `allowtransparency`, `color-scheme: light`, body bg transparent
- **Form elements**: auto-styled bare `<button>`, `<input[range]>`, headings
- **SVG utilities**: `.t .ts .th .box .arr .leader` classes injected
- **Color ramp**: `.c-red` → `.c-green` (6 colors) for SVG shapes

### 6.3 Collapsible Thinking (Claude Pattern)
- Header = clickable button + chevron (was rail dot + static title)
- Collapsed by default in balanced mode
- Click to expand/collapse any interval
- Live streaming: always expanded with pulse dot

### 6.4 Vietnamese Diacritics
- **45+ labels fixed**: reasoning-labels.ts, InterleavedBlockSequence, ReasoningInterval
- "Dieu huong" → "Điều hướng", "Tra cuu" → "Tra cứu", etc.

### 6.5 Serif Editorial Prose
- Editorial flow prose dùng Newsreader (serif font)
- Lead, body, tail copy all inherit serif

**Files:** `visual_tools.py`, `InlineVisualFrame.tsx`, `InlineHtmlWidget.tsx`, `ReasoningInterval.tsx`, `InterleavedBlockSequence.tsx`, `globals.css`, `reasoning-labels.ts`, `_settings.py`

---

## 7. Token Streaming V2

**Vấn đề:** Streaming bursty, choppy, cắt giữa chữ.
**Giải pháp — 5-layer engine:**

| Layer | Mô tả |
|-------|--------|
| Adaptive Pacing | `bufferDepth / targetBufferDepth` → scale chars/frame |
| Ease-in | Cubic smoothstep t²(3-2t) over 15 frames |
| Word Boundary | ±6 chars search, snap to space/punctuation |
| Markdown Guard | Don't break **, ```, __, ~~ clusters |
| Drain Mode | `end()` → buffer*0.25/frame accelerated |

**Config:** initialHoldMs=80, easeInFrames=15, targetBufferDepth=40, min=3, max=28

**Files:** `stream-buffer.ts`, `stream-buffer.test.ts`

---

## 8. Thinking Indicator

**Vấn đề:** 1-10s wait sau gửi message — không có visual feedback.
**Giải pháp:**
- Minimal-clean: spinner + shimmer text "Đang suy nghĩ..."
- Shimmer: Wiii orange `#ff643b` + gold `#f0d080` sweep
- Spinner: light gray `#c8c8d8` CSS border animation
- Auto-hides khi streaming blocks arrive
- Cursor `|` chỉ hiện khi chưa có content nào

**Files:** `MessageList.tsx`, `globals.css`

---

## 9. Research Reports

| Report | Path |
|--------|------|
| Visual System Handoff | `.claude/reports/SPRINT-228-229-VISUAL-SYSTEM-HANDOFF.md` |
| Logo Generation Prompts | `.claude/reports/LOGO-GENERATION-PROMPTS.md` |
| UX/UI Audit | `.claude/reports/UX-UI-AUDIT-2026-03-14.md` |
| SEO Submission Guide | `.claude/reports/SEO-SUBMISSION-GUIDE.md` |
| Claude Cowork Research | `.claude/reports/CLAUDE-COWORK-RESEARCH-2026-03-14.md` |
| Scaling 1000 Users | `.claude/reports/SCALING-1000-USERS-GUIDE.md` |
| V5 Remaining Gaps | `.claude/reports/V5-REMAINING-GAPS-2026-03-15.md` |
| Thinking UX Issues | `.claude/reports/THINKING-UX-ISSUES-2026-03-16.md` |

---

## 10. Vấn đề CẦN TEAM CODEX Fix

### P0 — Critical

| Issue | Mô tả | Root Cause |
|-------|--------|-----------|
| **Thinking intervals isLive** | Chevron collapsible không hoạt động vì intervals luôn `live` | Backend không finalize interval state sau streaming complete. Cần rebuild Docker. |
| **Text duplicate thinking→prose** | Cùng text hiện trong thinking interval VÀ prose answer | Backend emit cùng content vào cả `thinking` và `answer` SSE events |

### P1 — Important

| Issue | Mô tả |
|-------|--------|
| **Multi-figure routing** | AI chọn `tool_generate_rich_visual` (legacy) thay vì `tool_generate_visual` (structured). Cần force structured tool trong direct agent. |
| **Widget inline rendering** | Widget HTML render nhưng chỉ khi stream complete, không during streaming. SSE streaming buffer splits widget fence. |

### P2 — Nice to have

| Issue | Mô tả |
|-------|--------|
| Custom SVG diagrams | Templates dùng HTML text lists thay vì SVG (sẽ tự giải quyết khi structured visual path hoạt động) |
| Inline code badge | `<code>` đã styled nhưng có thể cần tune theo brand |

---

## 11. Test Status

| Suite | Tests | Status |
|-------|-------|--------|
| Backend visual tools | 48 | ✅ PASS |
| Backend visual intent | 13 | ✅ PASS |
| Frontend interleaved blocks | 19 | ✅ PASS |
| Frontend stream buffer | 21 | ✅ PASS |
| Frontend widget routing | 7 | ✅ PASS |

---

## 12. Production Status

- **URL:** https://wiii.holilihu.online/
- **VM:** GCP e2-medium (asia-southeast1-b)
- **Container:** `wiii-app-local:latest` (Docker)
- **Nginx:** dist-web copied vào `wiii-nginx` container
- **Deployment guide:** `.claude/reports/SCALING-1000-USERS-GUIDE.md`

**QUAN TRỌNG:** Mỗi lần deploy frontend, PHẢI copy dist-web vào Nginx:
```bash
sudo docker cp wiii-desktop/dist-web/. wiii-nginx:/usr/share/nginx/html/
```
