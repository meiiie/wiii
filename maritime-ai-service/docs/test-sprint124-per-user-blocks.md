# Test Plan: Sprint 124 — Per-User Character Blocks

**Ngày:** 2026-02-18
**Tester:** [Tên đồng nghiệp]
**Mục tiêu:** Xác nhận character blocks (bộ nhớ sống của Wiii) đã được cách ly theo từng user

---

## Tổng quan thay đổi

Trước Sprint 124: Tất cả user dùng chung 4 character blocks (rò rỉ dữ liệu).
Sau Sprint 124: Mỗi user có bộ character blocks riêng biệt.

---

## Chuẩn bị

### Yêu cầu
- Server Wiii đang chạy: `http://localhost:8000`
- API Key: `local-dev-key` (hoặc key cấu hình trong `.env`)
- Tool test API: Postman, curl, hoặc Wiii Desktop app

### Kiểm tra server
```bash
curl http://localhost:8000/api/v1/health
# Expect: {"status":"ok","service":"Wiii",...}
```

---

## Test Case 1: API — User mới có blocks rỗng

**Mục đích:** User mới KHÔNG thấy data của user khác.

```bash
curl -s http://localhost:8000/api/v1/character/state \
  -H "X-API-Key: local-dev-key" \
  -H "X-User-ID: tester-new-user-001" \
  -H "X-Role: student"
```

**Kết quả mong đợi:**
```json
{
    "blocks": [],
    "total_blocks": 0
}
```

**PASS nếu:** `total_blocks = 0` hoặc tất cả blocks có `content = ""`.
**FAIL nếu:** Thấy nội dung của user khác (như "SOLAS Chapter III", "Luật Hàng hải").

---

## Test Case 2: API — User cũ (global) vẫn thấy data cũ

**Mục đích:** Backward compatibility — data cũ không bị mất.

```bash
curl -s http://localhost:8000/api/v1/character/state \
  -H "X-API-Key: local-dev-key" \
  -H "X-User-ID: __global__" \
  -H "X-Role: student"
```

**Kết quả mong đợi:**
```json
{
    "blocks": [
        {"label": "favorite_topics", "content": "...(có nội dung)...", ...},
        {"label": "learned_lessons", "content": "...(có nội dung)...", ...},
        ...
    ],
    "total_blocks": 4
}
```

**PASS nếu:** `total_blocks = 4` và `favorite_topics`, `learned_lessons` có nội dung.

---

## Test Case 3: Chat — 2 users khác nhau, Wiii nhớ đúng người

**Mục đích:** Khi chat, Wiii không trộn lẫn thông tin giữa 2 user.

### Bước 1: Chat với User A

Mở Wiii Desktop hoặc gửi API:

**Settings/Headers:**
- `X-User-ID: tester-user-A`
- `X-Session-ID: session-A-001`

**Prompt 1 (User A):**
```
Xin chào Wiii! Mình là Hùng, mình đang học về MARPOL Annex I.
Mình muốn biết về quy định xả dầu trên biển.
```

**Prompt 2 (User A):**
```
Mình rất thích chủ đề về ô nhiễm biển và muốn tìm hiểu thêm về MARPOL Annex IV (nước thải).
```

> Đợi Wiii trả lời xong. Background tasks cần ~10s để lưu facts.

### Bước 2: Kiểm tra blocks của User A

```bash
curl -s http://localhost:8000/api/v1/character/state \
  -H "X-API-Key: local-dev-key" \
  -H "X-User-ID: tester-user-A" \
  -H "X-Role: student"
```

**PASS nếu:** Nếu có blocks, nội dung liên quan đến "Hùng", "MARPOL", "ô nhiễm biển".

### Bước 3: Chat với User B

**Settings/Headers:**
- `X-User-ID: tester-user-B`
- `X-Session-ID: session-B-001`

**Prompt 1 (User B):**
```
Chào Wiii! Tôi là Mai, tôi đang tìm hiểu về COLREGs Rule 13 (Overtaking).
Cho tôi biết khi nào tàu được coi là đang vượt tàu khác?
```

**Prompt 2 (User B):**
```
Tôi thích chủ đề an toàn hàng hải và đèn tín hiệu. Tôi muốn học thêm về COLREGs Part C (Lights and Shapes).
```

### Bước 4: Kiểm tra blocks của User B

```bash
curl -s http://localhost:8000/api/v1/character/state \
  -H "X-API-Key: local-dev-key" \
  -H "X-User-ID: tester-user-B" \
  -H "X-Role: student"
```

**PASS nếu:** Nếu có blocks, nội dung liên quan đến "Mai", "COLREGs", "đèn tín hiệu" — KHÔNG có "Hùng", "MARPOL".

### Bước 5: Kiểm tra cross-check — User A không bị ảnh hưởng

```bash
curl -s http://localhost:8000/api/v1/character/state \
  -H "X-API-Key: local-dev-key" \
  -H "X-User-ID: tester-user-A" \
  -H "X-Role: student"
```

**PASS nếu:** Blocks của User A vẫn giữ nguyên, KHÔNG có thông tin của User B.

---

## Test Case 4: DB — Kiểm tra trực tiếp database

```bash
docker exec wiii-postgres psql -U wiii -d wiii_ai -c \
  "SELECT user_id, label, length(content) as chars, version
   FROM wiii_character_blocks
   ORDER BY user_id, label;"
```

**PASS nếu:**
- Có cột `user_id` trong bảng
- Mỗi user có bộ blocks riêng (không trùng user_id)
- Data cũ nằm ở `user_id = '__global__'`

---

## Test Case 5: Wiii Desktop — Test trên giao diện

### Bước 1: Mở Wiii Desktop
- Settings → Connection → Nhập Server URL, API Key
- Settings → Người dùng → Nhập User ID = `desktop-tester-001`

### Bước 2: Chat bình thường
```
Chào Wiii! Mình muốn hỏi về SOLAS Chapter V - An toàn hàng hải.
```

### Bước 3: Mở Character Panel (nếu có)
- Click biểu tượng Character trên StatusBar hoặc Sidebar
- Kiểm tra blocks hiển thị

**PASS nếu:** Character Panel hiển thị blocks dành riêng cho `desktop-tester-001`, không lẫn data user khác.

---

## Test Case 6: Prompt không bị lẫn (kiểm tra gián tiếp)

**Mục đích:** Xác nhận system prompt chỉ chứa living state của đúng user.

### User C chat:
```
Headers: X-User-ID: tester-user-C
Prompt: "Wiii ơi, bạn có nhớ mình là ai không? Bạn biết gì về mình?"
```

**PASS nếu:** Wiii trả lời rằng chưa biết gì về user (vì user mới, chưa có character blocks).
**FAIL nếu:** Wiii nhắc đến thông tin của user A, B, hoặc bất kỳ ai khác.

---

## Lưu ý quan trọng

1. **Character tools chỉ ghi khi LLM quyết định**: Không phải mọi tin nhắn đều trigger ghi character note. Cần chat 3-5 lượt để Wiii bắt đầu ghi nhận.

2. **Background tasks cần thời gian**: Sau khi chat, đợi ~10-15 giây trước khi kiểm tra blocks.

3. **Routing ảnh hưởng character tools**: Character tools chỉ có ở DIRECT response node. Nếu câu hỏi được route đến RAG hoặc TUTOR, character tools không được gọi trực tiếp (nhưng pre-compaction flush vẫn extract facts).

4. **Empty blocks là bình thường**: User mới sẽ có 0 blocks ban đầu. Blocks được tạo tự động khi `compile_living_state()` được gọi lần đầu.

---

## Checklist tổng hợp

| # | Test | Kết quả | Ghi chú |
|---|------|---------|---------|
| 1 | User mới → blocks rỗng | [ ] PASS / [ ] FAIL | |
| 2 | __global__ → data cũ còn | [ ] PASS / [ ] FAIL | |
| 3a | User A chat → blocks riêng | [ ] PASS / [ ] FAIL | |
| 3b | User B chat → blocks riêng | [ ] PASS / [ ] FAIL | |
| 3c | Cross-check A ≠ B | [ ] PASS / [ ] FAIL | |
| 4 | DB có cột user_id | [ ] PASS / [ ] FAIL | |
| 5 | Desktop UI hiển thị đúng | [ ] PASS / [ ] FAIL | |
| 6 | Wiii không nhắc user khác | [ ] PASS / [ ] FAIL | |

**Tester ký:** _________________ **Ngày:** _________________
