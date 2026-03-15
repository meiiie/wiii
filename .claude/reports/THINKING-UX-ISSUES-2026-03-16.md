# Thinking UX Issues — Báo cáo chi tiết
**Date:** 2026-03-16
**Priority:** P0 — ảnh hưởng trực tiếp UX

---

## Issue 1: Thinking intervals chưa collapsible đúng

**Hiện tại:** Dots (●) hiện text nhưng KHÔNG có chevron expand/collapse
**Root cause:** `interval.isLive` luôn `true` ngay cả sau streaming complete → chevron ẩn
**Fix đã deploy:** Chevron luôn hiện (Sprint V5-F5) nhưng có thể chưa rebuild Docker backend

**Action:**
- Rebuild Docker image (backend cần update để finalize interval state)
- Verify `reasoning-interval--complete` class xuất hiện sau stream xong

---

## Issue 2: `|` cursor sau thinking

**Hiện tại:** Sau dòng cuối thinking, hiện `|` cursor trước prose
**Root cause:** `streamingContent` trigger cursor pulse nhưng blocks chưa populated

**Fix cần:**
File: `wiii-desktop/src/components/chat/MessageList.tsx`
```tsx
// Thay condition:
{!visibleStreamingBlocks.length && (
// Bằng:
{!visibleStreamingBlocks.length && !streamingContent && (
```
Cursor chỉ hiện khi CHƯA CÓ content gì.

---

## Issue 3: Text duplicate (thinking → prose)

**Hiện tại:** Cùng text hiện trong thinking interval VÀ trong prose answer
**Root cause:** Backend emit cùng content trong cả `thinking` SSE event và `answer` SSE event
**Vị trí:** Likely in `graph_streaming.py` hoặc `stream_utils.py`

**Action:**
- Backend team cần review `_push_event` logic
- Thinking content KHÔNG nên duplicate vào answer text
- Hoặc: frontend cần deduplicate thinking text khỏi answer prose

---

## Issue 4: Shimmer thinking indicator

**Brief từ Hùng:** Shimmer text dùng màu cam `#ff643b` + vàng kim `#f0d080`
**Đã deploy:** CSS gradient shimmer nhưng dùng `--text-tertiary` (gray) thay vì orange
**File JSX tham khảo:** `C:\Users\Admin\Downloads\wiii-thinking-v2.jsx` — per-character shimmer rAF

**Action:** Cập nhật shimmer colors theo brief:
- Text: `var(--accent)` hoặc `#ff643b`
- Highlight: `#f0d080` (gold)
- Spinner: `#c8c8d8` (light gray)

---

## Tham khảo:
- `C:\Users\Admin\Downloads\wiii-thinking-v2.jsx` — Full demo component
- `C:\Users\Admin\Downloads\wiii-thinking-team-brief.md` — Design intent + API
- Claude thinking pattern: thin collapsed line + chevron expand
