# Wiii Thinking Recovery Check

> Date: 2026-03-26
> Scope: narrator fast-fallback quality after semantic thinking patch
> Status: targeted backend patch complete, unit regression green

## 1. Mục tiêu của đợt vá này

Đợt này không nhắm vào việc làm response hay hơn, vì response hiện tại đã khá tốt.

Mục tiêu là kéo **thinking** về gần mốc Wiii ban đầu hơn:

- bớt echo prompt
- bớt generic planner voice
- bớt self-monitoring kiểu "giữ phần tự thân"
- bớt lặp action-intention ở visual turn
- tăng cảm giác inner voice thật của Wiii theo loại turn

## 2. Những gì đã đổi

File chính:

- `maritime-ai-service/app/engine/reasoning/reasoning_narrator.py`

Tests:

- `maritime-ai-service/tests/unit/test_reasoning_narrator_runtime.py`

Thay đổi cốt lõi:

1. Bổ sung semantic fallback thinking theo turn-type:
   - emotional
   - identity
   - knowledge
   - visual
   - simulation
   - relational/general

2. Chặn thêm các cụm generic cũ khỏi visible thinking:
   - `Mình đang chắt lấy điều cốt lõi...`
   - `Mình vẫn đang nghe thêm xem nhịp này...`
   - `Mình đã nắm được điều chính...`
   - `Khâu dữ liệu lại thành một câu trả lời đủ chắc và đủ gần`

3. `action_text` giờ chỉ xuất hiện khi thật sự đổi bước:
   - `act`
   - `transition`

4. Dùng semantic observation nếu observation thực sự có nghĩa,
   không dùng observation mang tính operational/tool trace.

## 3. Kết quả cục bộ sau patch

### A. Emotional

Prompt:

```text
buon qua
```

Thinking mới:

```text
Đọc câu này, mình thấy trong đó có một khoảng chùng xuống.

Lúc này điều quan trọng nhất không phải giải thích gì nhiều, mà là ở lại với bạn cho thật dịu.

Mình sẽ mở lời nhẹ thôi, để nếu bạn muốn kể tiếp thì đã có chỗ để tựa vào.
```

### B. Identity

Prompt:

```text
ban la ai?
```

Thinking mới:

```text
Câu này mình muốn đáp thẳng và gần thôi.

Không cần dựng thêm lớp nào cả, chỉ cần nói ra mình là ai.
```

Prompt:

```text
ten gi?
```

Thinking mới:

```text
Câu này chỉ cần một nhịp đáp thật gần là đủ.

Mình sẽ nói tên mình ra thật gọn, rồi để cuộc trò chuyện mở ra tự nhiên.
```

Prompt:

```text
cuoc song the nao?
```

Thinking mới:

```text
Câu này chạm vào phía đời sống của mình nhiều hơn là một thông tin khô.

Mình muốn đáp lại bằng một nhịp thật hơn, để bạn thấy hôm nay Wiii đang sống như thế nào.
```

### C. Visual

Prompt:

```text
Visual cho minh xem thong ke du lieu hien tai gia dau may ngay gan day
```

Thinking mới:

```text
Mình đang gom vài mốc đủ đáng tin trước, để phần nhìn ra không chỉ đẹp mà còn có ý.

Điều mình muốn giữ ở yêu cầu trực quan này là: liếc một mắt đã thấy được xu hướng chính.

Mình sẽ dựng từ cái khung dễ đọc nhất trước, rồi mới thêm lớp giải thích.
```

Action ở `attune`:

```text
(rỗng)
```

Action ở `act`:

```text
Để mình kéo vài mốc đáng tin rồi dựng phần nhìn gọn cho bạn.
```

### D. Simulation

Prompt:

```text
mo phong 3d duoc khum
```

Thinking mới:

```text
Việc mô phỏng này cần một khung đủ rõ để chuyển động và quan hệ không bị rối.

Mình đang chọn thứ nên hiện ra trước, để bạn nhìn là hiểu chứ không chỉ thấy cho đẹp.

Mình sẽ dựng từ một sân khấu gọn trước rồi mới mở rộng.
```

## 4. Verify

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'; python -m pytest tests/unit/test_reasoning_narrator_runtime.py -v -p no:capture --tb=short
```

Kết quả:

```text
15 passed in 3.21s
```

`py_compile`:

```text
ok
```

## 5. Đánh giá thật

Đợt vá này đã giúp thinking:

- sống hơn rõ rệt ở emotional turn
- bớt meta ở identity turn
- bớt generic ở visual/simulation turn
- bớt lặp action text

Nhưng đây **chưa phải đích cuối**.

Các điểm còn phải bám tiếp:

1. runtime live có thể vẫn còn echo/lẫn lớp ở vài path không đi qua fallback narrator đẹp
2. knowledge turn/RAG/Tutor có thể vẫn leak chút technical residue ở gray rail
3. frontend rail vẫn cần được kiểm lại nếu gray rail còn gộp thứ không nên gộp

## 6. Verdict

Patch này là một bước **kéo thinking trở lại mốc Wiii cũ** khá rõ ở tầng local narrator.

Nó chưa chứng minh toàn bộ live runtime đã đạt,
nhưng đã sửa đúng chỗ tệ nhất và tạo được nền tốt hơn để test E2E tiếp.
