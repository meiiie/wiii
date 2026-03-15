# V5 Remaining Gaps — Handoff cho team tiếp theo
**Date:** 2026-03-15
**Status:** 4 gaps chưa đạt Claude parity

---

## Gap 1: Inline Code Badge

**Claude:** `softmax(QK^T)V` hiển thị như monospace pill (rounded bg, monospace font)
**Wiii:** Chưa có — inline code chỉ là `<code>` mặc định

### Cách triển khai:

**CSS** (`globals.css`):
```css
/* Inline code badge — Claude pattern */
.markdown-content code:not(pre code) {
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: var(--bg3);
  color: var(--red, #ef4444);
  padding: 2px 6px;
  border-radius: 5px;
  font-weight: 500;
}
```

**Đã có sẵn** trong `_DESIGN_CSS` (visual_tools.py) class `.code-badge`. Cần apply tương tự cho markdown inline code trong `MarkdownRenderer` hoặc `RichMarkdownSegment`.

**Files cần sửa:**
- `wiii-desktop/src/styles/globals.css` — thêm inline code style
- Hoặc `wiii-desktop/src/styles/markdown.css` nếu có

**Effort:** 15 phút

---

## Gap 2: Color Ramp SVG Classes

**Claude:** Host inject `.c-purple`, `.c-blue`, `.c-teal` etc. vào iframe figure. Model viết `<rect class="c-purple"/>` → tự động có màu.
**Wiii:** Chưa có — model phải hard-code màu trong mỗi visual.

### Cách triển khai:

**File:** `wiii-desktop/src/components/common/InlineVisualFrame.tsx` → function `buildVisualFrameDocument()`

Thêm vào phần host CSS inject:
```css
/* Color ramp classes — apply to SVG shapes */
g.c-red > rect, rect.c-red { fill: light-dark(#fef2f2, #3b1111); stroke: light-dark(#fca5a5, #f87171); }
g.c-blue > rect, rect.c-blue { fill: light-dark(#eff6ff, #1e3a5f); stroke: light-dark(#93c5fd, #60a5fa); }
g.c-teal > rect, rect.c-teal { fill: light-dark(#f0fdfa, #0d3331); stroke: light-dark(#5eead4, #2dd4bf); }
g.c-purple > rect, rect.c-purple { fill: light-dark(#f5f3ff, #2d1b69); stroke: light-dark(#c4b5fd, #a78bfa); }
g.c-amber > rect, rect.c-amber { fill: light-dark(#fffbeb, #3b2e0a); stroke: light-dark(#fcd34d, #fbbf24); }
g.c-green > rect, rect.c-green { fill: light-dark(#ecfdf5, #0d3320); stroke: light-dark(#6ee7b7, #34d399); }

/* SVG text utilities */
.t { font-size: 14px; fill: var(--wiii-text); }
.ts { font-size: 12px; fill: var(--wiii-text-secondary); }
.th { font-size: 14px; fill: var(--wiii-text); font-weight: 600; }
.arr { stroke: var(--wiii-text-tertiary); fill: none; stroke-width: 1.5; }
.box { fill: var(--wiii-bg-secondary); stroke: var(--wiii-border); }
.leader { stroke: var(--wiii-text-tertiary); stroke-width: 0.5; stroke-dasharray: 4 3; fill: none; }
```

Cũng thêm vào `_DESIGN_CSS` trong `visual_tools.py` để legacy visuals cũng có.

**Files cần sửa:**
- `wiii-desktop/src/components/common/InlineVisualFrame.tsx` — buildVisualFrameDocument()
- `maritime-ai-service/app/engine/tools/visual_tools.py` — _DESIGN_CSS

**Effort:** 30 phút

---

## Gap 3: Multiple Small Figures Per Response

**Claude:** Explanatory query → 3-7 small figures, mỗi figure chứng minh 1 claim
**Wiii:** Thường chỉ 1 figure — planner có nhưng chưa trigger đúng

### Root Cause:

1. `enable_structured_visuals=True` đã bật → `tool_generate_visual` available
2. Nhưng AI vẫn chọn `tool_generate_rich_visual` (legacy) vì:
   - Force tool logic (`_direct_required_tool_names`) force `tool_generate_rich_visual`
   - Tool hints describe legacy tool more prominently
3. Structured tool có figure planner (1-3 figures) nhưng chưa được force

### Cách triển khai:

**File:** `maritime-ai-service/app/engine/multi_agent/graph.py`

1. Sửa `_direct_required_tool_names()`:
```python
# Khi visual intent detected, force tool_generate_visual thay vì tool_generate_rich_visual
if any(signal in normalized for signal in visual_signals):
    if settings.enable_structured_visuals:
        required.append("tool_generate_visual")  # structured path
    else:
        required.append("tool_generate_rich_visual")  # legacy path
```

2. Sửa tool hints trong `_build_direct_tools_context()`:
```python
# Ưu tiên tool_generate_visual khi structured visuals enabled
if settings.enable_structured_visuals:
    tool_hints.append(
        "- tool_generate_visual: UU TIEN — tạo visual giáo dục article-first. "
        "Tự động chia thành 1-3 figures tùy độ phức tạp."
    )
```

3. Sửa `_build_code_studio_tools_context()` tương tự.

4. Sửa `filter_tools_for_visual_intent()` trong `visual_intent_resolver.py` để ưu tiên structured tool.

**Files cần sửa:**
- `maritime-ai-service/app/engine/multi_agent/graph.py` — force tool + hints
- `maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py` — tool filtering

**Effort:** 1-2 giờ (cần test kỹ để không break routing)

### Lưu ý quan trọng:
- Structured visual path (`tool_generate_visual`) trả về `VisualPayloadV1` JSON, KHÔNG phải `widget` code block
- Frontend xử lý qua SSE `visual` event → `VisualBlock` component
- Khác hoàn toàn với legacy path (`widget` code block → `splitWidgetBlocks` → `InlineHtmlWidget`)
- Cần đảm bảo SSE visual event pipeline hoạt động end-to-end

---

## Gap 4: Host-Owned Form Element Styling

**Claude:** Bare `<button>`, `<input>`, `<select>`, `<input type="range">` tự động styled bởi host
**Wiii:** Partial — `InlineVisualFrame.buildVisualFrameDocument()` đã có form styling nhưng chưa đầy đủ

### Cách triển khai:

**File:** `wiii-desktop/src/components/common/InlineVisualFrame.tsx` → `buildVisualFrameDocument()`

Kiểm tra và bổ sung styling cho:
```css
/* Button defaults */
button:not([class]) {
  padding: 6px 14px;
  font-size: 13px;
  background: transparent;
  color: var(--wiii-text);
  border: 0.5px solid var(--wiii-border);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
button:not([class]):hover { background: var(--wiii-bg-secondary); }
button:not([class]):active { transform: scale(0.98); }

/* Range slider */
input[type="range"] {
  -webkit-appearance: none;
  width: 100%;
  height: 3px;
  background: light-dark(rgba(0,0,0,0.08), rgba(255,255,255,0.1));
  border-radius: 2px;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--wiii-bg);
  border: 1px solid var(--wiii-border);
  cursor: pointer;
}

/* Headings */
h1, h2, h3, h4, h5, h6 { color: var(--wiii-text); }
```

**Files cần sửa:**
- `wiii-desktop/src/components/common/InlineVisualFrame.tsx` — buildVisualFrameDocument()

**Effort:** 30 phút

---

## Tóm tắt effort:

| Gap | Effort | Priority |
|-----|--------|----------|
| Inline code badge | 15 phút | P2 (cosmetic) |
| Color ramp SVG classes | 30 phút | P2 (enables better SVG figures) |
| Multi-figure (2-3 per response) | 1-2 giờ | **P0 (biggest UX gap)** |
| Host form element styling | 30 phút | P1 (simulation/quiz UX) |

**Ưu tiên:** Gap 3 (multi-figure) > Gap 4 (form styling) > Gap 2 (SVG classes) > Gap 1 (code badge)

---

## Files tham khảo từ Claude HTML:

- `C:\Users\Admin\Downloads\Kimi linear attention visualization - Claude.html` — main response HTML
- `C:\Users\Admin\Downloads\Kimi linear attention visualization - Claude_files\saved_resource(1).html` — Claude host design system (fonts + form styling + SVG utilities + color ramps)
- `C:\Users\Admin\Downloads\Kimi linear attention visualization - Claude_files\mcp_apps.html` — MCP app proxy iframe

---

## Tham khảo kiến trúc:

- [Claude builds visuals](https://claude.com/blog/claude-builds-visuals)
- [Interactive tools in Claude](https://claude.com/blog/interactive-tools-in-claude)
- [MCP Apps](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- [OpenGenerativeUI](https://github.com/CopilotKit/OpenGenerativeUI)
- Claude HTML export: `saved_resource(1).html` — host design system reference
