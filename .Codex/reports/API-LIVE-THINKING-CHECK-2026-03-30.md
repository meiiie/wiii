# API Live Thinking Check - 2026-03-30

## Muc tieu

Kiem tra runtime that qua API local sau patch:

- `POST /api/v1/chat`
- `POST /api/v1/chat/stream/v3`

## Dieu kien local

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:1420`
- Postgres local da duoc bat lai qua Docker compose (`wiii-postgres`, port `5433`)

## Kiem tra 1: prompt ngan `oke`

Endpoint:
- sync chat

Ket qua:
- HTTP `200`
- answer: `Mình là Wiii! Bạn muốn tìm hiểu gì hôm nay?`

Nhung log backend cho thay direct path bi loi:
- `[DIRECT] LLM generation failed: name 'build_response_language_instruction' is not defined`

He qua:
- runtime van tra duoc answer fallback
- nhung day la regression that o direct lane

## Kiem tra 2: prompt tutor `Giải thích Quy tắc 15 COLREGs`

### Sync

Ket qua:
- HTTP `200`
- agent metadata: `tutor`
- answer ra duoc va noi dung hop le

Nhung:
- `metadata.thinking_content = ""`
- `metadata.thinking = ""`

=> sync transport hien tai van chua surface visible thinking ra response metadata.

### Stream

Ket qua:
- HTTP `200`
- co `thinking_start/thinking_delta/thinking_end`

Raw stream cho thay:

1. Dot thinking dau ra tieng Viet:
- `Tôi vừa bắt đầu tìm kiếm "Rule 15 COLREGs"...`

2. Sau tool result, stream van do ra mot block thinking dai bang tieng Anh:
- `**Wiii Tutor's Deep Dive into Rule 15 (Again!)**`
- `Oh my, the user is asking about Rule 15 again!`
- `I should start by confirming...`
- `I'll greet them in Vietnamese...`

=> patch language alignment chua tac dong dung vao runtime path nay.

## Current truth

Runtime that hien tai van con 3 van de:

1. `direct` lane co regression do missing symbol:
- `build_response_language_instruction` undefined

2. `tutor sync` van khong surfacing thinking:
- `thinking_content` rong

3. `tutor stream` van phat native thought answer-planning bang tieng Anh:
- language alignment rat mong chua hit dung runtime path that

## Ket luan

Unit tests dang xanh, nhung runtime API da chi ra rang:
- patch chua duoc tich hop dung den visible-thinking path that cua tutor
- va co them mot direct-lane regression khac can sua truoc khi danh gia thinking chat luong that tren UI
