# UX/UI Audit Report — Wiii AI Web App
**URL:** https://wiii.holilihu.online/
**Date:** 2026-03-14
**Auditor:** Claude Opus 4.6 (AI Lead)
**Benchmark:** Claude.ai, ChatGPT, Gemini, Perplexity (March 2026)

---

## 1. Tổng quan đánh giá

| Tiêu chí | Điểm (1-10) | Ghi chú |
|-----------|-------------|---------|
| Visual Design | 7.5/10 | Warm palette đẹp, nhưng thiếu polish ở details |
| Typography | 8/10 | Manrope + Newsreader tốt, hierarchy rõ |
| Layout | 7/10 | Desktop OK, không responsive mobile |
| Interaction Design | 6.5/10 | Animations smooth, nhưng thiếu micro-interactions |
| Information Architecture | 7/10 | Sidebar + chat + settings logic, nhưng đông tính năng |
| Accessibility | 7.5/10 | ARIA labels, focus-visible, reduced motion OK |
| Empty States | 5/10 | Welcome screen OK, nhưng settings/sidebar trống |
| Error Handling | 5.5/10 | Toast notifications có, nhưng inline errors yếu |
| Loading States | 6/10 | Thinking blocks OK, nhưng skeleton screens thiếu |
| Consistency | 7/10 | Design system tốt, nhưng có chỗ inconsistent |

**Tổng: 6.7/10** — Solid foundation, cần polish để đạt mức premium.

---

## 2. So sánh với đối thủ (March 2026)

### 2.1 Claude.ai
| Feature | Claude | Wiii | Gap |
|---------|--------|------|-----|
| Welcome screen | Centered, clean, 3 suggestion tiles | Centered, clean, 3 suggestions | Tương đương |
| Sidebar | Collapsible, project folders | Collapsible, search | Claude có folders |
| Message bubbles | Transparent AI, subtle user bg | Transparent AI, cream user bg | Tương đương |
| Thinking indicator | "Claude is thinking..." spinner | Multi-step thinking blocks | **Wiii tốt hơn** |
| Dark mode | Yes (polished) | Yes (có nhưng cần polish) | Claude mượt hơn |
| Mobile responsive | Yes (full responsive) | **Không có** | **Gap lớn** |
| Inline visuals | Artifacts + inline visuals | Widget system (cần fix render) | Claude tốt hơn |
| File upload | Drag-drop + click | Click only | Claude tốt hơn |

### 2.2 ChatGPT
| Feature | ChatGPT | Wiii | Gap |
|---------|---------|------|-----|
| Welcome screen | Centered, 4 suggestion cards | Centered, 3 suggestions | Tương đương |
| Voice input | Yes (microphone button) | **Không có** | Gap |
| Model selector | Dropdown in input | Domain selector | Khác concept |
| Canvas/Artifacts | Side panel | Inline widget | Khác approach |
| Keyboard shortcuts | Cmd+K command palette | **Không rõ** | Cần check |

### 2.3 Gemini
| Feature | Gemini | Wiii | Gap |
|---------|--------|------|-----|
| Material Design 3 | Google's design system | Custom Tailwind | Gemini consistent hơn |
| Suggestion chips | Below input, animated | Below input, static | Gemini polish hơn |
| Extensions | Google services integration | LMS integration | Khác target |

---

## 3. Vấn đề cụ thể và Giải pháp

### 🔴 CRITICAL (Fix ngay)

#### 3.1 Mobile Responsive — Không có
**Hiện tại:** Desktop-only (min-width cố định, sidebar 288px)
**Vấn đề:** User trên mobile thấy layout bể hoặc phải zoom
**Benchmark:** Claude/ChatGPT responsive đầy đủ
**Fix:**
```
- Breakpoint sm (640px): Sidebar overlay thay vì push
- Breakpoint md (768px): Sidebar auto-collapse
- Input luôn full-width trên mobile
- Message bubbles max-width 100% trên mobile
```
**Priority:** P0 — user chính dùng web trên điện thoại/tablet

#### 3.2 Avatar/Mascot chưa dùng đúng
**Hiện tại:** Orange blob generic ("W" trên nền cam) làm avatar trong chat
**Vấn đề:** Không giống mascot kawaii đã chọn. Avatar trong chat nên là mascot.
**Fix:** Thay Wiii avatar trong chat bằng mascot PNG (ảnh 3 — kawaii face)
**Files:** `WiiiAvatar.tsx`, `public/` images

#### 3.3 "User" thay vì tên thật
**Hiện tại:** "Chào buổi chiều, User!" khi đăng nhập dev mode
**Vấn đề:** Không personal, giảm engagement
**Fix:** Prompt nhập tên khi first login, hoặc dùng "bạn" thay "User"

---

### 🟡 HIGH (Cải thiện sớm)

#### 3.4 Settings Page — Thiếu nội dung
**Hiện tại:** "Lĩnh vực kiến thức: Chưa có lĩnh vực" — empty, uninformative
**Fix:**
- Thêm default domain "Hàng hải" nếu chưa chọn
- Thêm description cho mỗi field
- Thêm avatar upload
- "Đăng xuất" button nên có icon + confirm dialog

#### 3.5 Sidebar Empty State
**Hiện tại:** "Chưa có cuộc trò chuyện nào. Nhấn ✨ để bắt đầu nha!"
**Fix:**
- Thêm illustration/icon cho empty state
- Larger text, friendly tone
- Quick action button (không chỉ text link)

#### 3.6 Chat Input — Thiếu Micro-interactions
**Hiện tại:** Send button luôn hiện, không có character count visible
**Benchmark:** Claude dims send button khi input trống, ChatGPT có voice button
**Fix:**
- Send button disabled/dimmed khi input trống
- Show character count khi gần limit (>8000/10000)
- Subtle expand animation khi focus input
- Keyboard shortcut hint: "Enter gửi · Shift+Enter xuống dòng" (đã có, nhưng quá nhạt)

#### 3.7 Thinking Blocks — Quá chi tiết
**Hiện tại:** Hiện nhiều step: ĐIỀU HƯỚNG, BẮT NHỊP, KIỂM DỮ LIỆU, CHUYỂN BƯỚC...
**Vấn đề:** User bình thường bị overwhelm bởi technical details
**Benchmark:** Claude chỉ hiện "Thinking..." với spinner đơn giản
**Fix:**
- Default: Chỉ hiện 1 dòng summary ("Đang suy nghĩ...")
- Expandable: Click để xem chi tiết (cho advanced users)
- Hoặc: Gộp thành progress bar thay vì nhiều blocks riêng

#### 3.8 Status Bar — Quá technical
**Hiện tại:** "maritime" domain label ở bottom-left, context % bottom-right
**Vấn đề:** User không hiểu "1% | 138 tin"
**Fix:** Ẩn khi không streaming. Chỉ hiện khi có action đang xảy ra.

---

### 🟢 MEDIUM (Nice to have)

#### 3.9 Welcome Screen Suggestions — Cần context-aware
**Hiện tại:** Cố định 3 suggestions (COLREGs, SOLAS, MARPOL)
**Fix:**
- Rotate suggestions theo thời gian trong ngày
- Personalize theo conversation history
- Thêm trending topics

#### 3.10 Dark Mode Polish
**Hiện tại:** Dark mode có nhưng contrast ở một số chỗ yếu
**Fix:**
- Review contrast ratios (WCAG AA: 4.5:1)
- Đảm bảo borders visible trong dark mode
- Test tất cả components trong dark mode

#### 3.11 Onboarding Flow
**Hiện tại:** Không có onboarding — user đăng nhập → thẳng vào chat
**Benchmark:** ChatGPT có tooltips, Claude có "Getting Started" section
**Fix:**
- First-time user: 3-step onboarding (giới thiệu Wiii, chọn domain, thử hỏi)
- Tooltip highlights cho features mới (living agent, visual tools)

#### 3.12 Command Palette
**Hiện tại:** Không rõ có command palette không
**Benchmark:** Claude có Cmd+K, Notion có Cmd+K
**Fix:** Thêm Cmd+K (hoặc Ctrl+K) command palette cho power users

#### 3.13 Message Actions — Hover-to-reveal
**Hiện tại:** Copy, regenerate, like/dislike buttons visible mọi lúc
**Fix:** Ẩn khi không hover (giống Claude) — cleaner look

#### 3.14 Smooth Scroll to Bottom
**Hiện tại:** Auto-scroll khi streaming, nhưng có thể abrupt
**Fix:** Smooth scroll with "New messages ↓" floating button khi scroll lên

---

## 4. Design Token Recommendations

### 4.1 Spacing Scale (tham khảo Tailwind + Material Design 3)
```
4px  (1)  — tight internal padding
8px  (2)  — standard gap
12px (3)  — section padding
16px (4)  — card padding
24px (6)  — major section gap
32px (8)  — page margins
48px (12) — hero spacing
```

### 4.2 Elevation/Shadow System
```
Level 0: flat (no shadow) — default
Level 1: var(--shadow-sm) — cards, input fields
Level 2: var(--shadow-md) — dropdowns, floating elements
Level 3: var(--shadow-lg) — modals, overlays
```
(Đã có trong globals.css — consistent)

### 4.3 Color Usage Guidelines
```
Primary (terracotta #C75B39): CTA buttons, active states, links
Teal (#2C84DB): Info, tool results, secondary accent
Green (#1a8a4a): Success, online status
Red: Error, destructive actions
Surface hierarchy: surface > surface-secondary > surface-tertiary
```

---

## 5. Action Plan (Prioritized)

### Sprint 231 — Quick Wins (1-2 days)
- [ ] Send button disabled khi input trống
- [ ] Fix "User" → prompt tên hoặc dùng "Bạn"
- [ ] Thinking blocks: default collapsed, 1 dòng summary
- [ ] Status bar: ẩn khi idle
- [ ] Message actions: hover-to-reveal

### Sprint 232 — Mobile Responsive (3-5 days)
- [ ] Breakpoints: sm (640px), md (768px), lg (1024px)
- [ ] Sidebar: overlay mode trên mobile (<768px)
- [ ] Chat input: full-width trên mobile
- [ ] TitleBar: ẩn trên web (không cần window controls)
- [ ] Test trên iPhone/Android Chrome

### Sprint 233 — Polish & Delight (2-3 days)
- [ ] Mascot avatar trong chat thay vì orange blob
- [ ] Settings page redesign (avatar upload, domain selector)
- [ ] Sidebar empty state illustration
- [ ] Onboarding 3-step cho first-time users
- [ ] Dark mode contrast audit

### Sprint 234 — Power Features (3-5 days)
- [ ] Command palette (Ctrl+K)
- [ ] Keyboard shortcuts panel
- [ ] Context-aware suggestions
- [ ] "New messages ↓" floating button
- [ ] Drag-drop file upload

---

## 6. Tham khảo

- [Conversational AI UI Comparison 2025](https://intuitionlabs.ai/articles/conversational-ai-ui-comparison-2025)
- [Claude vs ChatGPT vs Gemini 2026](https://improvado.io/blog/claude-vs-chatgpt-vs-gemini-vs-deepseek)
- [Material Design 3](https://m3.material.io/)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Nielsen Norman Group — AI UX](https://www.nngroup.com/articles/ai-ux/)
