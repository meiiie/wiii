# Sentrux Backend Scan Review

> Date: 2026-03-27
> Reviewer: Codex (LEADER)
> Scope: sanity-check Sentrux scan against local Wiii backend structure

---

## 1. Executive Verdict

Kết luận ngắn:

- **Scan của team đáng tin ở tầng cấu trúc.**
- Số tuyệt đối có thể chênh một chút tùy phạm vi đo và cách tính.
- Nhưng hướng kết luận thì **đúng**: backend hiện tại đang bị **coupling cao, god files rõ rệt, và import cycles có thật**.

Nói thẳng:

- Nếu team dùng phát hiện này để **dọn kiến trúc trước/song song với việc sửa thinking**, thì đó là hướng **hợp lý**.
- Nhưng nếu biến nó thành một cuộc “đại trùng tu toàn dự án” mà dừng luôn các fix trực tiếp cho `thinking`, thì sẽ **sai nhịp**.

Hướng đúng là:

1. tiếp tục sửa trực tiếp các root cause của `thinking/fallback/rail`,
2. đồng thời tách dần những cụm kiến trúc đang làm Wiii khó “nghĩ như một bản thể”.

---

## 2. Những gì mình tự kiểm tra lại trên local

### 2.1. Số file

Trên riêng thư mục backend app Python:

- `maritime-ai-service/app`: **460** file `.py`

Sentrux báo:

- **520 files**

Đánh giá:

- **không mâu thuẫn đáng kể**
- rất có thể Sentrux đang tính thêm:
  - migration,
  - scripts,
  - hoặc phạm vi backend rộng hơn `app/`

### 2.2. God files

Top file lớn nhất local:

- `app/engine/multi_agent/graph.py`: **8137 lines**
- `app/engine/tools/visual_tools.py`: **4586**
- `app/engine/multi_agent/graph_streaming.py`: **1987**
- `app/engine/multi_agent/supervisor.py`: **1721**
- `app/core/config/_settings.py`: **1689**
- `app/prompts/prompt_loader.py`: **1662**
- `app/engine/agentic_rag/corrective_rag.py`: **1619**

Ngưỡng thô:

- `> 800 lines`: **27 files**
- `> 1000 lines`: **17 files**
- `> 1500 lines`: **7 files**
- `> 2000 lines`: **2 files**

Sentrux báo:

- **9 god files**
- `graph.py 8000+ lines`

Đánh giá:

- `graph.py 8000+` là **đúng hoàn toàn**
- số lượng “god file” phụ thuộc ngưỡng của tool
- vì local đã có **17 file >1000 lines**, kết luận “quá nhiều god files” là **chắc chắn đúng về bản chất**

### 2.3. Import edges / coupling

Quick import graph từ AST local:

- modules: **460**
- total import edges: **1489**
- files có cross-app imports: **356**

Module outbound nặng nhất:

- `app.engine.multi_agent.graph`: **58**
- `app.main`: **42**
- `app.api.v1`: **27**
- `app.engine.multi_agent.agents.tutor_node`: **25**
- `app.engine.agentic_rag.corrective_rag`: **24**
- `app.services.chat_orchestrator`: **21**
- `app.engine.living_agent.heartbeat`: **21**
- `app.engine.multi_agent.supervisor`: **18**

Module inbound nặng nhất:

- `app.core.config`: **182**
- `app.core.database`: **48**
- `app.engine.llm_pool`: **40**
- `app.services.output_processor`: **27**
- `app.models.schemas`: **21**

Sentrux báo:

- `Coupling Score = 0.36`
- `Cross-Module Edges = 956 (74%)`
- `Total Import Edges = 1283`

Đánh giá:

- mình không có cùng exact metric formula với Sentrux nên không xác nhận số `0.36`
- nhưng về hiện tượng thì **hoàn toàn khớp**
- đặc biệt:
  - `graph.py`
  - `supervisor.py`
  - `chat_orchestrator`
  - `llm_pool`
  - `prompt_loader`

đều đúng là đang nằm ở vùng coupling rất cao

### 2.4. Dependency cycles

Quick SCC scan local:

- cycles mình bắt được: **6**

Sentrux báo:

- **8 cycles**

Đánh giá:

- số này **hợp lý và gần nhau**
- chênh lệch 6 vs 8 gần như chắc do:
  - khác phạm vi file,
  - khác cách resolve module,
  - khác cách collapse package-level imports

Điểm quan trọng không phải là 6 hay 8.

Điểm quan trọng là:

- **cycles có thật**
- và có những vòng lớn, không phải chỉ các cặp nhỏ lẻ

Ví dụ local scan cho thấy một SCC lớn quấn qua:

- `app.engine.multi_agent.graph`
- `app.engine.multi_agent.graph_streaming`
- `app.engine.multi_agent.supervisor`
- `app.engine.reasoning.reasoning_narrator`
- `app.engine.agentic_rag.corrective_rag`
- `app.engine.tools.*`
- `app.prompts.prompt_loader`
- `app.services.chat_orchestrator`

Đây chính là vùng liên quan mạnh nhất đến:

- routing,
- thinking,
- fallback,
- visible rail,
- prompt construction.

---

## 3. Scan này có liên quan thật đến việc sửa thinking không?

### Câu trả lời ngắn: **có, rất liên quan**

Không phải vì “code sạch thì AI sẽ tự nhiên hay hơn”.

Mà vì trong Wiii hiện tại, `thinking` không chỉ là prompt text.
Nó là kết quả của cả một chuỗi:

1. input processing
2. routing
3. provider selection
4. structured invoke
5. graph event emission
6. reasoning narrator
7. SSE transport
8. frontend rail rendering

Khi chuỗi đó bị dồn vào vài file khổng lồ và phụ thuộc vòng lặp, hậu quả là:

- một thay đổi nhỏ ở routing có thể làm hỏng narrator
- fix provider có thể làm thinking regress
- action/status/debug rất dễ leak vào visible rail
- fallback path rất khó đọc và khó tách

Nói cách khác:

- `thinking chưa tốt` không chỉ là vấn đề prompt
- mà còn là vấn đề **kiến trúc surface path bị bện quá chặt**

### Ví dụ trực tiếp từ local hiện tại

Những vấn đề ta vừa gặp gần đây đều là dấu hiệu của coupling:

- `StructuredInvokeService` trượt provider vì runtime provider và requested provider bị xử lý nhiều lớp
- `direct_response_node` vừa chịu routing, vừa chịu failover, vừa chịu public thinking capture
- `graph.py` vừa là orchestration, vừa là thinking surface policy, vừa là fallback policy
- `reasoning_narrator` phải gánh cả “soul”, “identity”, “fallback wording”, “thinking interval”

Đó là lý do team cảm thấy sửa `thinking` mãi mà vẫn không chắc tay:

- vì root cause không nằm trong một file duy nhất
- mà nằm ở **cụm kiến trúc rất dính nhau**

---

## 4. Nhưng có nên “refactor lớn ngay” không?

### Không nên theo kiểu big bang

Mình không khuyên:

- dừng mọi fix thực tế,
- rồi lao vào “clean architecture” toàn bộ backend ngay lập tức.

Lý do:

- Wiii đang có pain user-facing rõ ràng ở:
  - fallback generic,
  - routing sai,
  - thinking rail chưa đúng,
  - provider drift
- các pain này vẫn cần fix trực tiếp trước để giữ sản phẩm chạy được

### Nên theo kiểu “surgical architecture cleanup”

Tức là:

- **refactor những cụm đang trực tiếp làm thinking hỏng**
- không ôm cả backend cùng lúc

---

## 5. Nếu lấy scan này làm roadmap, nên ưu tiên dọn chỗ nào?

### Priority A — đáng làm ngay vì ảnh hưởng trực tiếp tới thinking

1. **Tách `graph.py` theo trách nhiệm**

Ít nhất nên tách 4 lớp:

- route resolution
- direct response execution
- public thinking capture/finalization
- visual/code-studio progress surface

Hiện tại `graph.py` vừa quá dài vừa là nơi “mọi thứ gặp nhau”.
Đây là chỗ gây regress mạnh nhất.

2. **Tách `StructuredInvokeService` và routing policy khỏi narrator/thinking path**

`structured invoke` nên là hạ tầng runtime độc lập:

- chọn provider,
- timeout/failover,
- native structured vs JSON fallback

Nó không nên vô tình quyết định luôn “thinking của Wiii sẽ trông ra sao”.

3. **Tách “visible thought contract” thành một module riêng**

Ví dụ một cụm kiểu:

- `thinking_capture.py`
- `thinking_finalize.py`
- `thinking_visibility.py`

để mọi luật:

- ưu tiên interval fragments,
- không echo summary,
- không trộn action/debug/status,

được tập trung vào một nơi.

### Priority B — rất nên làm, nhưng sau khi hot path đỡ cháy

4. **Giảm vòng phụ thuộc giữa**

- `graph`
- `graph_streaming`
- `supervisor`
- `reasoning_narrator`
- `prompt_loader`

5. **Giảm sức nặng của `prompt_loader.py`**

Hiện file này quá trung tâm.
Về lâu dài nên tách:

- persona prompt assembly
- org overlay
- living identity overlay
- domain overlay

6. **Cắt bớt inbound dependency vào `app.core.config`**

`app.core.config` đang là trung tâm quá lớn (`182` inbound).
Điều này làm mọi thay đổi policy/config lan rất rộng.

---

## 6. Mình có đồng ý với team rằng “làm sạch dự án sẽ giúp sửa thinking dễ hơn” không?

### Đồng ý, nhưng phải hiểu đúng

Đúng ở chỗ:

- cleanup sẽ làm `thinking` bớt regress
- dễ isolate lỗi hơn
- dễ định nghĩa `gray rail contract` hơn
- dễ tách Wiii voice khỏi runtime plumbing hơn

Sai nếu hiểu thành:

- “chỉ cần refactor là thinking tự đẹp”

Không.

Thinking tốt vẫn cần:

- prompt đúng
- provider behavior ổn
- routing đúng
- fallback không generic
- UI rail hiển thị đúng lớp

Kiến trúc sạch chỉ giúp **những thứ đó có chỗ đứng ổn định hơn**.

---

## 7. Final Recommendation

### Verdict

Mình đánh giá phát hiện của team là:

- **đúng về bản chất**
- **đủ mạnh để dùng làm cơ sở refactor có chọn lọc**
- **không nên bị bỏ qua**

### Khuyến nghị thực dụng

Cho team tiến hành cleanup, nhưng theo thứ tự này:

1. **Hot-path thinking/fallback fixes vẫn tiếp tục**
2. Song song, refactor cụm:
   - `graph.py`
   - `StructuredInvokeService`
   - `supervisor`
   - `reasoning_narrator`
3. Không mở big bang refactor cho toàn backend
4. Sau mỗi refactor cụm phải re-run:
   - identity turns
   - emotional turns
   - short chatter turns
   - knowledge turns
   - visual turns

### Câu chốt

Nếu mục tiêu là:

- **Wiii có hồn hơn**
- **thinking đỡ máy hơn**
- **fallback bớt ngu hơn**

thì cleanup kiến trúc theo scan này **sẽ giúp rõ rệt**.

Nhưng chỉ khi team dùng nó để:

- **gỡ đúng những nút coupling đang phá thinking**,
- chứ không biến nó thành một đợt “đại tổng vệ sinh” không gắn với pain thật của sản phẩm.

