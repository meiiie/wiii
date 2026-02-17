# Sprint 74: Streaming Quality & Performance — Test Report

**Date**: 2026-02-13 22:22:56
**User**: `test-sprint74` | **Session**: `s74-stream-v2`
**Endpoint**: `http://localhost:8000/api/v1/chat/stream/v3` (SSE)

---

## Summary

| Turn | Label | Time (ms) | TTFT (ms) | Answer Events | Status Events | Thinking Events |
|------|-------|-----------|-----------|---------------|---------------|-----------------|
| 1 | Turn 1: Giới thiệu bản thân (Memory) | 14084 | 12783 | 27 | 6 | 4 |
| 2 | Turn 2: Kiến thức domain (Tutor — TTFT c | 35673 | 26990 | 154 | 7 | 7 |
| 3 | Turn 3: Sở thích + điểm yếu (Memory) | 42211 | 22924 | 147 | 9 | 7 |
| 4 | Turn 4: Kiến thức personalized (Tutor —  | 41952 | 25076 | 180 | 9 | 7 |
| 5 | Turn 5: Recall memory | 10221 | 9146 | 22 | 6 | 4 |
| 6 | Turn 6: Update info | 9617 | 8686 | 19 | 6 | 4 |
| 7 | Turn 7: Final recall | 10373 | 9155 | 25 | 6 | 4 |

---

## Sprint 74 Feature Verification

| Check | Status | Detail |
|-------|--------|--------|
| Guardian | ✅ PASS | Guardian: status-only (no empty thinking blocks) |
| No thinking leak in answer | ✅ PASS | No thinking leak in answer |
| Answer length | ✅ PASS | Answer length: 75 words (within limit) |
| TTFT | ⚠️ WARN | TTFT: 26990ms (>= 25s — improvement needed) |
| Grader | ✅ PASS | Grader: status-only (no empty thinking blocks) |

---

## Turn 1: Turn 1: Giới thiệu bản thân (Memory)

**Input**: `Xin chào, tên mình là Hải, 28 tuổi, giảng viên hàng hải ở Hải Phòng. Mình đang chuẩn bị cho kỳ thi COLREGs.`

### Event Counts
```
  answer: 27
  done: 1
  metadata: 1
  status: 6
  thinking_end: 2
  thinking_start: 2
  TOTAL: 39
```

### Timing
- Total: **14084ms**
- First answer token (TTFT): **12783ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 2064 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 2081 | `status` | Kiểm tra an toàn |
| 5687 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 5700 | `thinking_start` | Phân tích câu hỏi |
| 5717 | `status` | → 🧠 Truy xuất bộ nhớ |
| 5731 | `thinking_end` |  |
| 12734 | `status` | 🧠 Truy xuất bộ nhớ |
| 12753 | `thinking_start` | Truy xuất bộ nhớ |
| 12769 | `thinking_end` |  |
| 12783-14037 | `answer` | (27 chunks streamed) |
| 14037 | `status` | 📝 Tổng hợp câu trả lời |
| 14053 | `metadata` |  |
| 14068 | `done` |  |

### Answer Preview

> Chào Hải nhé! Wiii đã nhớ kỹ thông tin của bạn rồi nè.
> 
> Wiii ghi nhận là bạn hiện đang ở Hải Phòng thay vì Đà Nẵng như trước đây nhé. Các thông tin khác như bạn 28 tuổi, là giảng viên hàng hải và đang ôn thi COLREGs thì mình vẫn nhớ rất rõ.
> 
> Chúc bạn ôn tập thật tốt cho kỳ thi quan trọng này, cần hỗ trợ gì cứ bảo Wiii nha!

*(324 chars, ~75 words)*

---

## Turn 2: Turn 2: Kiến thức domain (Tutor — TTFT check)

**Input**: `Giải thích Quy tắc 15 COLREGs về tình huống giao cắt cho mình nhé`

### Event Counts
```
  answer: 154
  done: 1
  metadata: 1
  status: 7
  thinking: 1
  thinking_end: 3
  thinking_start: 3
  tool_call: 1
  tool_result: 1
  TOTAL: 172
```

### Timing
- Total: **35673ms**
- First answer token (TTFT): **26990ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 3 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 23 | `status` | Kiểm tra an toàn |
| 2162 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 2173 | `thinking_start` | Phân tích câu hỏi |
| 2188 | `status` | → 👨‍🏫 Tạo bài giảng |
| 2203 | `thinking_end` |  |
| 2236 | `thinking_start` | Suy nghĩ (lần 1) |
| 5970 | `thinking_end` |  |
| 5992 | `tool_call` | {'name': 'tool_knowledge_search', 'args': {'query': 'Rule 15 COLREGs crossing situation nội dung chi tiết'}, 'id': '5978ac34-1611-48de-8286-27cc03e32ca5'} |
| 19218 | `tool_result` | {'name': 'tool_knowledge_search', 'result': 'Chào bạn, tôi là Wiii. Dựa trên kiến thức tổng quát (chưa được xác minh từ tài liệu gốc), nội dung chi tiết của Quy tắc 15 COLREGs về tình huống hai tàu đi cắt hướng nhau như sau:\n\nKhi hai tàu máy đang đi cắt hướng nhau đến mức có nguy cơ đâm va, tàu nào nhìn thấy tàu kia ở mạn phải của mình thì phải nhường đường cho tàu kia. Nếu điều kiện hoàn cảnh cho phép, tàu phải nhường đường cần tránh đi cắt ngang qua phía trước mũi của tàu kia.\n\nTóm lại, trong tình huống cắt hướng:\n- Tàu có tàu khác bên m', 'id': '5978ac34-1611-48de-8286-27cc03e32ca5'} |
| 26990-31162 | `answer` | (154 chunks streamed) |
| 31162 | `status` | 👨‍🏫 Tạo bài giảng |
| 31183 | `status` | 👨‍🏫 Đã phân tích từ 1 nguồn |
| 31198 | `thinking_start` | Giảng dạy |
| 31214 | `thinking` | [RAG Analysis] **Quá trình suy nghĩ:**  1. **Phân tích độ phức tạp câu hỏi**: Độ phức tạp: simple, D... |
| 31229 | `thinking_end` |  |
| 35631 | `status` | 📝 Tổng hợp câu trả lời |
| 35643 | `metadata` |  |
| 35658 | `done` |  |

### Answer Preview

> **Quy tắc 15** - **Tình huống cắt hướng** (Crossing situation) là một trong những bài học "vỡ lòng" nhưng cực kỳ quan trọng mà bất kỳ người đi biển nào cũng phải nằm lòng để tránh những cú va chạm không đáng có trên đại dương bao la.
> 
> Bạn cứ tưởng tượng thế này cho dễ nhớ nhé: Theo nội dung của **COLREGs**, khi hai tàu máy đang tiến về phía nhau theo hướng cắt ngang mà có nguy cơ đâm va, thì **tàu nào nhìn thấy tàu kia ở mạn phải của mình** sẽ là tàu phải **nhường đường**. Trong giới đi biển, tụ...

*(1725 chars, ~371 words)*

---

## Turn 3: Turn 3: Sở thích + điểm yếu (Memory)

**Input**: `Mình thích học qua ví dụ thực tế, nhưng hay nhầm giữa Quy tắc 14 và 15`

### Event Counts
```
  answer: 147
  done: 1
  metadata: 1
  status: 9
  thinking: 1
  thinking_end: 3
  thinking_start: 3
  tool_call: 1
  tool_result: 1
  TOTAL: 167
```

### Timing
- Total: **42211ms**
- First answer token (TTFT): **22924ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 7 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 28 | `status` | Kiểm tra an toàn |
| 5014 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 5026 | `thinking_start` | Phân tích câu hỏi |
| 5041 | `status` | → 👨‍🏫 Tạo bài giảng |
| 5056 | `thinking_end` |  |
| 5071 | `thinking_start` | Suy nghĩ (lần 1) |
| 7295 | `thinking_end` |  |
| 7313 | `tool_call` | {'name': 'tool_knowledge_search', 'args': {'query': 'Quy tắc 14 và Quy tắc 15 COLREGs ví dụ thực tế phân biệt'}, 'id': 'e4ea77e7-ae97-4a46-aba2-26f06811cdf1'} |
| 21677 | `tool_result` | {'name': 'tool_knowledge_search', 'result': '⚠️ Câu trả lời có thể không chính xác do thiếu nguồn tham khảo\n\nChào bạn, tôi là Wiii. Dưới đây là giải thích ngắn gọn về sự khác biệt giữa Quy tắc 14 và Quy tắc 15 của COLREGs dựa trên kiến thức tổng quát (lưu ý thông tin này chưa được xác minh từ tài liệu gốc trong cơ sở dữ liệu):\n\n**1. Quy tắc 14: Tình huống đối hướng (Head-on situation)**\n*   **Đặc điểm:** Hai tàu máy đi ngược chiều nhau hoặc gần như ngược chiều trên các đường thẳng đối diện, dẫn đến nguy cơ va chạm.\n*   **Hành động:** Cả ha', 'id': 'e4ea77e7-ae97-4a46-aba2-26f06811cdf1'} |
| 22924-28677 | `answer` | (147 chunks streamed) |
| 28677 | `status` | 👨‍🏫 Tạo bài giảng |
| 28692 | `status` | 👨‍🏫 Đã phân tích từ 1 nguồn |
| 28709 | `thinking_start` | Giảng dạy |
| 28724 | `thinking` | **Quá trình suy nghĩ:**  1. **Phân tích độ phức tạp câu hỏi**: Độ phức tạp: moderate, Domain: True  ... |
| 28740 | `thinking_end` |  |
| 36530 | `status` | ✅ Kiểm tra chất lượng |
| 36547 | `status` | ✅ Chất lượng: 10/10 |
| 42161 | `status` | 📝 Tổng hợp câu trả lời |
| 42181 | `metadata` |  |
| 42196 | `done` |  |

### Answer Preview

> **Quy tắc 14** và **Quy tắc 15** thực ra rất dễ phân biệt nếu bạn tưởng tượng mình đang cầm lái giữa biển khơi bao la, nơi mà những con sóng đôi khi làm ta rối trí. Hãy để tôi giúp bạn "vạch lá tìm đường" nhé!
> 
> **Quy tắc 14** - **Tình huống đối hướng (Head-on)**: Hãy tưởng tượng bạn đang đi bộ trong một hành lang hẹp và gặp một người đi ngược chiều đâm thẳng về phía mình. Để không đụng nhau, cả hai đều tự giác lách sang bên phải. Trên biển cũng vậy, khi hai tàu đi ngược chiều (hoặc gần như ngược...

*(1660 chars, ~359 words)*

---

## Turn 4: Turn 4: Kiến thức personalized (Tutor — TTFT check)

**Input**: `So sánh Quy tắc 14 và Quy tắc 15 giúp mình, dùng ví dụ thực tế nhé`

### Event Counts
```
  answer: 180
  done: 1
  metadata: 1
  status: 9
  thinking: 1
  thinking_end: 3
  thinking_start: 3
  tool_call: 1
  tool_result: 1
  TOTAL: 200
```

### Timing
- Total: **41952ms**
- First answer token (TTFT): **25076ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 6 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 26 | `status` | Kiểm tra an toàn |
| 2554 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 2575 | `thinking_start` | Phân tích câu hỏi |
| 2591 | `status` | → 👨‍🏫 Tạo bài giảng |
| 2611 | `thinking_end` |  |
| 2622 | `thinking_start` | Suy nghĩ (lần 1) |
| 8167 | `thinking_end` |  |
| 8190 | `tool_call` | {'name': 'tool_knowledge_search', 'args': {'query': 'nội dung Quy tắc 14 và Quy tắc 15 COLREGs'}, 'id': '5175b4da-a931-4604-8a17-cd506de2e2b4'} |
| 18767 | `tool_result` | {'name': 'tool_knowledge_search', 'result': 'Chào bạn, tôi là **Wiii Tutor**. Rất vui được tiếp tục hỗ trợ bạn tìm hiểu về Luật xa lộ trên biển (COLREGs). \n\nDựa trên kiến thức đã có và để làm rõ hơn các tình huống thực tế, tôi xin trình bày chi tiết nội dung Quy tắc 14 và 15 như sau:\n\n### 1. Quy tắc 14: Tình huống đối hướng (Head-on situation)\nQuy tắc này áp dụng khi hai tàu máy đi ngược chiều nhau.\n\n*   **Điều kiện áp dụng:** Hai tàu máy đi đối hướng hoặc gần như đối hướng dẫn đến nguy cơ đâm va.\n*   **Hành động:** **Cả hai tàu** đều phải', 'id': '5175b4da-a931-4604-8a17-cd506de2e2b4'} |
| 25076-29933 | `answer` | (180 chunks streamed) |
| 29933 | `status` | 👨‍🏫 Tạo bài giảng |
| 29951 | `status` | 👨‍🏫 Đã phân tích từ 1 nguồn |
| 29968 | `thinking_start` | Giảng dạy |
| 29983 | `thinking` | [RAG Analysis] Người dùng yêu cầu trình bày nội dung Quy tắc 14 và Quy tắc 15 của COLREGs dựa trên n... |
| 29998 | `thinking_end` |  |
| 36364 | `status` | ✅ Kiểm tra chất lượng |
| 36379 | `status` | ✅ Chất lượng: 6/10 |
| 41906 | `status` | 📝 Tổng hợp câu trả lời |
| 41921 | `metadata` |  |
| 41937 | `done` |  |

### Answer Preview

> **Quy tắc 14** và **Quy tắc 15** giống như hai bài toán khác nhau về phép lịch sự và sự quyết đoán trên biển vậy bạn ạ. Biển rộng mênh mông nhưng đôi khi "oan gia ngõ hẹp", việc phân biệt rõ hai quy tắc này sẽ giúp bạn giữ cho con tàu của mình luôn an toàn và "đẹp mặt" với các đồng nghiệp tàu bạn.
> 
> Nói về **Quy tắc 14 (Tình huống đối hướng)**, đây là lúc hai tàu máy đi ngược chiều nhau, "mặt đối mặt". Trong tình huống này, không có ai là "ưu tiên" hơn ai cả. **Cả hai tàu** đều phải có trách nhiệ...

*(2046 chars, ~442 words)*

---

## Turn 5: Turn 5: Recall memory

**Input**: `Bạn nhớ gì về mình?`

### Event Counts
```
  answer: 22
  done: 1
  metadata: 1
  status: 6
  thinking_end: 2
  thinking_start: 2
  TOTAL: 34
```

### Timing
- Total: **10221ms**
- First answer token (TTFT): **9146ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 15 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 31 | `status` | Kiểm tra an toàn |
| 2813 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 2817 | `thinking_start` | Phân tích câu hỏi |
| 2828 | `status` | → 🧠 Truy xuất bộ nhớ |
| 2845 | `thinking_end` |  |
| 9099 | `status` | 🧠 Truy xuất bộ nhớ |
| 9114 | `thinking_start` | Truy xuất bộ nhớ |
| 9130 | `thinking_end` |  |
| 9146-10176 | `answer` | (22 chunks streamed) |
| 10176 | `status` | 📝 Tổng hợp câu trả lời |
| 10191 | `metadata` |  |
| 10207 | `done` |  |

### Answer Preview

> Chào Hải! Wiii nhớ rõ về bạn chứ.
> 
> Bạn năm nay 28 tuổi, hiện đang là giảng viên hàng hải tại Hải Phòng. Mục tiêu quan trọng nhất của bạn lúc này là chuẩn bị thật tốt cho kỳ thi COLREGs sắp tới.
> 
> Cần mình hỗ trợ gì thêm cho việc ôn tập không, cứ bảo Wiii nhé!

*(258 chars, ~58 words)*

---

## Turn 6: Turn 6: Update info

**Input**: `Mình không còn ở Hải Phòng nữa, giờ mình chuyển về Đà Nẵng rồi`

### Event Counts
```
  answer: 19
  done: 1
  metadata: 1
  status: 6
  thinking_end: 2
  thinking_start: 2
  TOTAL: 31
```

### Timing
- Total: **9617ms**
- First answer token (TTFT): **8686ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 3 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 26 | `status` | Kiểm tra an toàn |
| 3141 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 3143 | `thinking_start` | Phân tích câu hỏi |
| 3165 | `status` | → 🧠 Truy xuất bộ nhớ |
| 3180 | `thinking_end` |  |
| 8641 | `status` | 🧠 Truy xuất bộ nhớ |
| 8656 | `thinking_start` | Truy xuất bộ nhớ |
| 8671 | `thinking_end` |  |
| 8686-9572 | `answer` | (19 chunks streamed) |
| 9572 | `status` | 📝 Tổng hợp câu trả lời |
| 9588 | `metadata` |  |
| 9602 | `done` |  |

### Answer Preview

> Chào Hải nhé! Wiii đã ghi nhớ là bạn không còn ở Hải Phòng nữa mà đã chuyển về Đà Nẵng rồi. 
> 
> Chúc bạn sớm ổn định tại thành phố mới để tiếp tục ôn luyện cho kỳ thi COLREGs thật tốt nhé. Có cần mình hỗ trợ gì thêm không?

*(220 chars, ~51 words)*

---

## Turn 7: Turn 7: Final recall

**Input**: `Tóm tắt tất cả thông tin bạn biết về mình đi`

### Event Counts
```
  answer: 25
  done: 1
  metadata: 1
  status: 6
  thinking_end: 2
  thinking_start: 2
  TOTAL: 37
```

### Timing
- Total: **10373ms**
- First answer token (TTFT): **9155ms**

### Event Timeline (key events)

| Time (ms) | Event | Content |
|-----------|-------|---------|
| 5 | `status` | 🚀 Bắt đầu xử lý câu hỏi... |
| 27 | `status` | Kiểm tra an toàn |
| 2891 | `status` | 🎯 Phân tích và định tuyến câu hỏi |
| 2908 | `thinking_start` | Phân tích câu hỏi |
| 2923 | `status` | → 🧠 Truy xuất bộ nhớ |
| 2938 | `thinking_end` |  |
| 9103 | `status` | 🧠 Truy xuất bộ nhớ |
| 9123 | `thinking_start` | Truy xuất bộ nhớ |
| 9139 | `thinking_end` |  |
| 9155-10328 | `answer` | (25 chunks streamed) |
| 10328 | `status` | 📝 Tổng hợp câu trả lời |
| 10343 | `metadata` |  |
| 10358 | `done` |  |

### Answer Preview

> Chào Hải! Wiii đã ghi nhớ những thông tin này về bạn nè:
> 
> - **Tên:** Hải.
> - **Tuổi:** 28 tuổi.
> - **Nơi ở:** Đà Nẵng.
> - **Nghề nghiệp:** Giảng viên hàng hải.
> - **Mục tiêu hiện tại:** Đang tập trung ôn luyện để chuẩn bị cho kỳ thi COLREGs.
> 
> Wiii luôn sẵn sàng hỗ trợ bạn ôn thi thật tốt nhé!

*(289 chars, ~61 words)*

---

## Performance Comparison (Sprint 73 → 74)

| Metric | Sprint 73 | Sprint 74 | Improvement |
|--------|-----------|-----------|-------------|
| Turn 2 TTFT | ~36000ms | 26990ms | Check |
| Turn 2 Total | ~46000ms | 35673ms | Improved |
| Turn 4 TTFT | ~36000ms | 25076ms | Check |
| Turn 4 Total | ~46000ms | 41952ms | Check |
