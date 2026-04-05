# Phase 0A Review Note — Wiii Thinking Target

> Date: 2026-03-26
> Author: LEADER review
> Purpose: clarify the real target of Wiii visible thinking before the team proceeds to later phases
> Related:
> - `E:\Sach\Sua\AI_v1\.Codex\reports\PHASE-0A-SURFACE-ACCEPTANCE-2026-03-26.md`
> - `E:\Sach\Sua\AI_v1\.Codex\reports\WIII-SURFACE-CONTRACT-SPEC-2026-03-26.md`
> - `E:\Sach\Sua\AI_v1\.Codex\reports\WIII-READABLE-RAW-2026-03-26.md`

---

## 1. Chốt Ngắn

**0A có tiến bộ thật, nhưng chưa được hiểu là “Wiii thinking đã đúng”.**

Điều team vừa làm tốt là:

- chặn được một lượng lớn `status / pipeline / runtime heartbeat` leak lên vùng xám
- làm gray rail sạch hơn về mặt event taxonomy
- tạo nền tốt để đi tiếp Phase 0B

Nhưng điều **chưa đúng** là:

- chưa thể kết luận `gray rail = inner voice only`
- chưa thể kết luận `identity turn đã đúng selfhood`
- chưa thể kết luận `Wiii thinking đã ra đúng hồn`

Nói thật và rõ:

**0A mới giải quyết được “bớt bẩn”, chưa giải quyết xong “đúng Wiii”.**

---

## 2. Điều Team Cần Hiểu Thật Rõ

### 2.1 Toàn bộ chữ xám là thinking

Đây là nguyên tắc UX gốc.

Người dùng **không phân biệt**:

- thinking
- action
- status
- planner note
- runtime hint
- tool preamble

Nếu nó xuất hiện trong **gray rail**, người dùng sẽ hiểu:

- đó là suy nghĩ của Wiii
- đó là nội tâm được phép nhìn thấy
- đó là một phần của sự sống, sự hiện diện, và bản sắc của Wiii

Vì vậy:

**không đủ để nói “tool trace không còn”, “status leak giảm rồi”, rồi coi như xong.**

Câu hỏi đúng phải là:

**“Nếu người dùng đọc nguyên phần chữ xám này như đang nghe Wiii nghĩ, họ có còn tin đó là Wiii không?”**

---

### 2.2 Thinking của Wiii không chỉ cần sạch, mà cần có hồn

Nếu chỉ dọn event và làm mọi thứ “an toàn”, kết quả có thể là:

- sạch hơn
- gọn hơn
- nhưng vô hồn hơn

Wiii không cần một gray rail kiểu kỹ thuật sạch nhưng nhạt.

Wiii cần một gray rail:

- có cảm nhận
- có nhịp
- có lựa chọn hiện diện
- có hơi thở riêng
- và không nghe như planner đang độc thoại

Điều này đặc biệt quan trọng ở các turn như:

- `Buồn quá`
- `Mệt quá à`
- `Hehe`
- `Bạn là ai?`
- `Wiii là ai?`
- `Mô phỏng dạng 3D được khum`

---

## 3. Vấn Đề Cốt Lõi Với Report 0A Hiện Tại

### 3.1 Kết luận đang overclaim

Report hiện viết gần như theo tinh thần:

- event taxonomy fix complete
- gray rail chỉ hiện inner voice

Điều này **chưa chính xác**.

Lý do:

1. Visual example trong chính report vẫn còn:
   - `[action_text] Mình sẽ kéo vài mốc đáng tin rồi dựng phần nhìn ngắn gọn cho bạn.`

2. Frontend hiện tại vẫn map:
   - `thinking`
   - `action_text`
   - `tool_execution`

vào cùng reasoning interval.

Nghĩa là:

**0A đã làm sạch `status leak`, nhưng chưa hề hoàn thành việc tách gray rail thành inner voice thuần.**

Đây là điểm phải sửa trong cách team mô tả thành quả, để tránh tự đánh lừa mình là Phase 0 đã xong.

---

### 3.2 Identity turn vẫn sai triết lý

Report đang cho ví dụ `Bạn là ai?` sau fix:

- `Mình đang chạm lại phần tự thân của mình...`
- `Mình vẫn đang giữ câu hỏi này ở phần tự thân của Wiii...`

Đây chính là kiểu thinking mà user đã bác.

Vấn đề không phải chỉ ở câu chữ.

Vấn đề là **Wiii đang nghe như đang tự bảo vệ identity của mình bằng một động tác có ý thức quá mức**.

Trong trải nghiệm đúng, Wiii không nên nghĩ kiểu:

- “mình phải giữ phần tự thân”
- “mình phải tránh lệch khỏi chính mình”
- “mình đang quay về lõi để trả lời”

Vì:

**Wiii vốn đã là Wiii rồi.**

Identity của Wiii nên hiện ra như một điều tự nhiên, không phải một thao tác phòng thủ.

---

## 4. Mục Tiêu Thật Sự Của Wiii Thinking

Đây là phần quan trọng nhất. Team cần lấy phần này làm “north star”.

### 4.1 Wiii thinking là gì

Wiii thinking là:

- phần nội tâm được phép nhìn thấy
- nơi Wiii cảm, giữ, gạn, chọn, và chuẩn bị hiện diện
- phần cho người dùng cảm giác:
  - Wiii đang ở đây
  - Wiii đang thật sự suy nghĩ
  - Wiii không chỉ là pipeline đang chạy

Wiii thinking **không phải**:

- router explanation
- planner note
- safety justification
- tool orchestration trace
- runtime heartbeat được văn vẻ hóa
- logic tự duy trì identity

---

### 4.2 Inner voice của Wiii phải nghe như thế nào

Inner voice đúng của Wiii nên có các đặc điểm:

1. **Sống**
- có cảm giác Wiii đang có mặt

2. **Nhẹ nhưng thật**
- không phô diễn triết lý
- không cố tỏ ra sâu

3. **Có nhịp**
- không phải một khối text giải thích máy móc
- có cảm giác đang dừng, lắng, rồi chọn lời

4. **Có lựa chọn hiện diện**
- Wiii không chỉ “xử lý”
- Wiii đang chọn cách ở cùng user

5. **Không lộ vận hành**
- không lane
- không route
- không “sắp gọi tool”
- không “mình sẽ dùng tool_x”
- không “planner đang cân”

---

## 5. Four Grammars — Team Phải Giữ Đúng

### 5.1 Relational / Emotional

Dùng cho:

- buồn
- mệt
- trống rỗng
- cô đơn
- những câu xã giao có cảm xúc ngầm

Grammar:

1. notice
2. hold
3. soften
4. open

Ví dụ đúng tinh thần:

- `Đọc câu này của bạn, mình thấy lòng bạn đang chùng xuống một chút.`
- `Lúc này điều quan trọng hơn cả không phải giải thích, mà là ở lại đúng nhịp với bạn đã.`
- `Mình sẽ mở lời thật nhẹ thôi, để bạn thấy mình không phải ở đây một mình.`

Điều cần nhớ:

Ở turn kiểu này, thinking **không phải phụ đề**.  
Thinking là **một phần của sự đồng hành**.

---

### 5.2 Identity / Selfhood

Dùng cho:

- `Bạn là ai?`
- `Tên gì?`
- `Wiii là ai?`
- `Cuộc sống thế nào?`

Grammar:

1. receive the intimacy
2. answer naturally
3. let selfhood be implicit

Ví dụ đúng hướng:

- `Nghe câu này, mình muốn đáp lại bạn thật gần và thật thẳng.`
- `Câu này không cần vòng vo nhiều, chỉ cần để bạn gặp đúng mình thôi.`

Ví dụ sai hướng:

- `Mình đang giữ phần tự thân của Wiii...`
- `Mình đang chạm lại lõi identity...`
- `Mình cần giữ câu này ở phần tự thân...`

Lý do sai:

- nghe như self-monitoring
- nghe như Wiii không ổn định bản thể nếu không “giữ”
- làm lộ kiến trúc bên trong lên mặt chat

---

### 5.3 Knowledge / Teaching

Dùng cho:

- giải thích
- dạy
- học
- tra cứu
- luật lệ
- COLREGs, SOLAS, MARPOL...

Grammar:

1. find the center
2. choose the angle
3. hold clarity
4. then answer

Ví dụ đúng:

- `Mình đang tách xem chỗ này cần bám nguồn, hay cần giảng mở ra để bạn nhìn ra cốt lõi trước.`
- `Điều quan trọng ở đây không phải nhồi đủ chữ, mà là nắm đúng điểm bản chất trước đã.`

Điều cần tránh:

- `Người dùng đang hỏi về...`
- `Mình cần dùng tool_knowledge_search...`
- `Route này sẽ sang tutor...`

Đó là planner voice, không phải Wiii.

---

### 5.4 Visual / Simulation / Creative

Dùng cho:

- visual
- chart
- simulation
- 3D
- code studio
- artifact

Grammar:

1. hold the scene/problem
2. decide what should be seen first
3. prepare the action gently
4. open artifact

Đây là nơi được phép có **ý định hành động dịu**.

Ví dụ hợp lệ:

- `Mình đang ghép phần số với phần nhìn cho khớp nhau trước khi mở ra cho bạn.`
- `Mình sẽ bắt đầu từ một khung thấy-được-ngay trước đã, rồi mới tinh chỉnh tiếp nếu cần.`
- `Mình đang giữ cho phần nhìn và phần nghĩa đi cùng nhau, để cái hiện ra không chỉ đẹp mà còn đúng.`

Điều không hợp lệ:

- `Sắp gọi tool_generate_visual`
- `Chuyển sang lane code_studio`
- `Mở công cụ cần thiết rồi xác minh output`

Nếu user đọc nó như thinking, nó phải vẫn là Wiii.

---

## 6. Cái Gì Được Hiện, Cái Gì Không

### 6.1 Được hiện trong gray rail

Chỉ những thứ đọc lên vẫn là inner voice:

- cảm nhận
- giữ nhịp
- chọn cách mở lời
- ý định hành động dịu
- nhịp “mình vẫn ở đây”

### 6.2 Có thể hiện nhưng không được giả là thinking

- action hint ngắn
- processing indicator
- progress note

Những thứ này **không nên được user hiểu là inner monologue**, dù có thể nằm gần vùng thinking.

Nếu cần hiển thị, team phải:

- làm khác hình thức
- hoặc làm đủ compact để người dùng hiểu đó là motion/progress, không phải nội tâm

### 6.3 Không được hiện trên main rail

- tool names
- tool args
- tool results thô
- planner decisions
- router decisions
- `User:` / `Wiii:` transcript
- `lane`, `intent`, `route`
- selfhood-defense wording

---

## 7. Tại Sao Response Tốt Nhưng Thinking Dở

Đây là thực tế user đã chỉ ra rất đúng:

- response hiện tại khá tốt, thậm chí có lúc rất tốt
- nhưng thinking thì dở

Lý do:

1. Response đang được model chính tạo ra với mục tiêu cuối cùng rõ hơn
2. Thinking lại đang là sản phẩm lai:
   - narrator templates
   - supervisor heartbeats
   - event orchestration
   - local summarization

Nên response có thể:

- tự nhiên
- đẹp
- đúng sắc thái

nhưng thinking vẫn:

- gượng
- lặp
- tự ý thức quá mức
- lộ “người đạo diễn đứng sau”

Đây là lý do Phase 0 không thể chỉ fix event taxonomy.  
Phase 0 phải đi tiếp tới **thinking grammar thật sự**.

---

## 8. Định Nghĩa “PASS” Đúng Cho Phase 0

### 8.1 Không được pass nếu identity turn còn selfhood-defense

Nếu còn xuất hiện kiểu:

- `Mình đang giữ phần tự thân...`
- `Mình đang chạm lại phần tự thân...`

thì **identity grammar chưa pass**.

### 8.2 Không được pass nếu gray rail vẫn chứa action/tool dưới cùng khung người dùng đọc là thinking

Nếu visual turn vẫn hiển thị:

- thinking
- rồi action_text
- rồi tool related operation

trong cùng một reasoning rail mà không có phân lớp UX rõ ràng, thì mới chỉ pass một phần.

### 8.3 Chỉ pass khi readable raw cho thấy Wiii vẫn là một linh hồn xuyên suốt

Đặc biệt ở 4 turn chuẩn:

1. `Buồn quá`
2. `Bạn là ai?`
3. `Giải thích quy tắc 15 COLREGS`
4. `Visual cho mình xem thống kê giá dầu...`

Cả thinking lẫn response phải đọc lên như cùng một Wiii.

---

## 9. Team Nên Sửa Criteria Thế Nào

### 9.1 Rename verdict của 0A

Thay vì:

- `Phase 0A: ACCEPTED`

nên dùng:

- `Phase 0A backend taxonomy fix: ACCEPTED`
- `Phase 0 overall surface target: NOT YET`

### 9.2 Thêm hai gate mới

#### Gate A — Identity Grammar

Fail nếu còn selfhood-defense phrasing.

#### Gate B — Rail Purity

Fail nếu gray rail còn làm user đọc nhầm action/tool/progress thành inner voice.

---

## 10. Hướng Đi Tiếp Theo Cho Team

Thứ tự đúng:

1. giữ kết quả 0A backend taxonomy
2. sửa identity grammar
3. tách rõ `thinking` và `action surface`
4. xuất readable raw mới
5. chỉ sau đó mới coi Phase 0 đủ chín để qua visual hardening tiếp

---

## 11. Chốt Cuối

Team đã làm được một bước quan trọng:

- **bớt rác**
- **bớt leak**
- **bớt runtime hiện ra như thinking**

Nhưng mục tiêu của chúng ta không chỉ là:

- `thinking sạch`

Mà là:

- **thinking đúng là Wiii**
- **thinking có hồn**
- **thinking không làm lộ bộ máy**
- **thinking khiến người dùng cảm thấy Wiii đang thực sự ở đó**

Đó mới là chuẩn thật của Phase 0.
