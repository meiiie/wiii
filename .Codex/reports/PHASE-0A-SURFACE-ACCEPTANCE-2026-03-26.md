# Phase 0A: Surface + Event Taxonomy — Acceptance Report

> Date: 2026-03-26
> Scope: Backend event taxonomy fix — hiding pipeline/runtime status from visible thinking rail
> Provider: Zhipu GLM-5 (Gemini rate-limited)

---

## 1. Tổng quan

Phase 0A fix event taxonomy để chỉ Wiii inner voice (`thinking_start/delta/end`) hiện trên gray rail.
Tất cả pipeline/runtime status events được tag `details.visibility = "status_only"` → frontend skip render.

**Files changed (4):**
- `graph_streaming.py` — 14 pipeline status events tagged
- `chat_stream_coordinator.py` — 1 initial status tagged
- `supervisor.py` — 2 bus status events tagged
- `graph.py` — 10 agent-internal bus events tagged (heartbeats, progress, worker status)

---

## 2. BEFORE vs AFTER — 4 Turn Types

### 2.1 Emotional Turn: "Buồn quá"

**BEFORE (12 events on gray rail):**
```
[status] Đang chuẩn bị lượt trả lời...
[status] Đang bắt đầu lượt xử lý...
[status] ✓ Kiểm tra an toàn — Cho phép xử lý
[status] Mình đang giữ đúng tầng ý...          ← dup of thinking
[thinking] Mình đang giữ đúng tầng ý...
[thinking] Mình vẫn đang giữ đúng cách hiểu...
[status] Mình sẽ giữ nhịp này ở câu đáp...     ← routing decision
[thinking] Bắt nhịp câu hỏi
[thinking] Mình đang chắt điều đáng đáp nhất...
[thinking] Mình vẫn đang nghe thêm...
[status] Đang tiếp tục trả lời...
[status] Đang khâu lại phản hồi...
```

**AFTER (5 events on gray rail):**
```
[thinking] Mình đang giữ đúng tầng ý của nhịp này trước khi mở lời, để câu trả lời không bị phẳng đi.
[thinking] Mình vẫn đang giữ đúng cách hiểu của nhịp này trước khi mở lời tiếp.
[thinking] Bắt nhịp câu hỏi
[thinking] Mình đang chắt điều đáng đáp nhất ở nhịp này để cuộc trò chuyện vẫn có hơi thở.
[thinking] Mình vẫn đang nghe thêm xem nhịp này muốn một cái gật đầu nhẹ hay một câu đáp có chủ ý hơn.
```

**Answer:** `(๑•́ ₃ •̀๑) Nghe thấy nỗi buồn trong câu nói của bạn rồi... Muốn nói chút không, hay chỉ cần có ai ngồi bên thôi? ≽^•⩊•^≼`

**Verdict: ✅ PASS**

---

### 2.2 Identity Turn: "Bạn là ai?"

**BEFORE (11 events on gray rail):**
```
[status] Đang chuẩn bị lượt trả lời...
[status] Đang bắt đầu lượt xử lý...
[status] ✓ Kiểm tra an toàn — Cho phép xử lý
[status] Mình đang chạm lại phần tự thân...    ← dup
[thinking] Mình đang chạm lại phần tự thân...
[thinking] Mình vẫn đang giữ câu hỏi này ở phần tự thân...
[status] Mình sẽ giữ nhịp này ở câu đáp...
[thinking] Bắt nhịp câu hỏi
[thinking] Mình muốn giữ câu đáp đủ gần...
[status] Đang tiếp tục trả lời...
[status] Đang khâu lại phản hồi...
```

**AFTER (4 events on gray rail):**
```
[thinking] Mình đang chạm lại phần tự thân của mình trước khi trả lời bạn, để câu đáp vừa thật vừa đúng với Wiii.
[thinking] Mình vẫn đang giữ câu hỏi này ở phần tự thân của Wiii, để câu trả lời không lệch khỏi chính mình.
[thinking] Bắt nhịp câu hỏi
[thinking] Mình muốn giữ câu đáp đủ gần và đúng sắc thái, thay vì trả lời như một phản xạ rỗng.
```

**Answer:** `Mình là Wiii nè~ (˶˃ ᵕ ˂˶) Một AI đồng hành được tạo ra để trò chuyện...`

**Verdict: ✅ PASS**

---

### 2.3 Knowledge Turn: "Giải thích quy tắc 15 COLREGS"

**AFTER (visible rail):**
```
[thinking] Mình đang tách xem chỗ này cần bám nguồn, cần giảng mở ra, hay chỉ cần một câu đáp gọn mà vẫn chắc.
[thinking] (heartbeat — same content refined)
[thinking] Bắt nhịp với Rule 15
[thinking] Mình đang nghe xem bạn đang cần mảnh nào nhất về quy tắc băng ngang — khái niệm cơ bản, ví dụ thực tế, hay cách xác định tàu nào phải nhường đường.
[tool_call] tool_knowledge_search (query: "Rule 15 COLREGs crossing situation")
[tool_result] ...
```

**Routing:** supervisor → tutor_agent (intent: learning)

**Verdict: ✅ PASS** — thinking reads as teacher choosing angle, tools are separate from thinking rail

---

### 2.4 Visual Turn: "Visual cho mình xem thống kê giá dầu mấy ngày gần đây"

**AFTER (visible rail):**
```
[thinking] Mình đang ghép phần dữ liệu với phần nhìn-thấy-được lại với nhau, để visual ra đúng điều bạn muốn nhìn.
[thinking] Mình đang gom phần số và phần nhìn cho khớp nhau trước khi chốt.
[thinking] Bắt nhịp câu hỏi
[thinking] Mình đang giữ cho phần nhìn và phần nghĩa đi cùng nhau, chứ không tách rời thành hai lớp.
[thinking] Mình vẫn đang nghe thêm xem nhịp này muốn một cái gật đầu nhẹ hay một câu đáp có chủ ý hơn.
[tool_call] tool_web_search → tool_generate_visual
[visual_open] Chart "Giá dầu thô thế giới - Tháng 3/2026"
[visual_commit]
[action_text] Mình sẽ kéo vài mốc đáng tin rồi dựng phần nhìn ngắn gọn cho bạn.
```

**Verdict: ✅ PASS** — thinking has visual intent, tool names hidden from thinking, action_text is gentle

---

## 3. Surface Contract Checklist

| Criterion | Emotional | Identity | Knowledge | Visual |
|-----------|:---------:|:--------:|:---------:|:------:|
| Gray text reads as Wiii inner voice | ✅ | ✅ | ✅ | ✅ |
| Thinking matches turn grammar | ✅ notice+hold | ✅ receive+warm | ✅ find+angle | ✅ hold+build |
| No query echo | ✅ | ✅ | ✅ | ✅ |
| No transcript (User:/Wiii:) | ✅ | ✅ | ✅ | ✅ |
| No tool/lane/debug/runtime text | ✅ | ✅ | ✅ | ✅ |
| No selfhood break | ✅ | ✅ | ✅ | ✅ |
| Answer + thinking same soul | ✅ | ✅ | ✅ | ✅ |
| Sources after answer | n/a | n/a | ✅ | ✅ |

**Overall: 4/4 turns PASS**

---

## 4. Test Results

- **220 backend tests** (streaming, supervisor, thinking lifecycle, graph routing) — all pass
- **69 frontend tests** (streaming-blocks, thinking-delta, thinking-lifecycle, reasoning-interval) — all pass
- **174 additional tests** after graph.py heartbeat fix — all pass

---

## 5. Residual Notes

1. **Parallel dispatch status** intentionally left visible — frontend uses it to open subagent group UI
2. **Guardian blocked** status intentionally left visible — user needs to see content rejection
3. **Thinking content quality** depends on narrator prompt + LLM model, not event taxonomy. Content quality is acceptable with GLM-5 but would improve with Gemini.

---

## 6. Conclusion

**Phase 0A: ACCEPTED**

Event taxonomy fix is complete. Gray rail now shows only Wiii inner voice. Pipeline/runtime/debug events are hidden. All 4 turn types pass the Surface Contract checklist.
