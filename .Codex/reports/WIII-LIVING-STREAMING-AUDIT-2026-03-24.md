# Wiii Living Streaming Audit — 2026-03-24

## Mục tiêu

Giữ Wiii theo hướng `quality-first` và `AI sống`:

- vẫn `LLM-first` cho supervisor/routing
- visible thinking phải hiện sớm và nghe như nội tâm của Wiii
- không để house identity bị vỡ khi provider đổi
- tôn trọng explicit provider pin khi người dùng chọn model cụ thể

## Đối chiếu kỹ thuật gần nhất

- Anthropic/Claude:
  - streaming event giàu ngữ nghĩa, ưu tiên `time-to-first-visible-progress`
  - visible thinking/tool streaming giúp người dùng thấy agent đang sống và đang làm việc
  - nguồn: <https://platform.claude.com/docs/en/build-with-claude/streaming>
  - nguồn: <https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency>
- OpenAI:
  - background/session cho tác vụ dài; stream cần resumable theo cursor/sequence
  - nguồn: <https://developers.openai.com/api/docs/guides/background>
- Vercel:
  - timeout/failover nên bám vào `first token / first progress`, không cắt bừa toàn task
  - nguồn: <https://vercel.com/docs/ai-gateway/models-and-providers/provider-timeouts>
- AIRI / Neuro-style systems:
  - bản sắc agent sống ở conductor/story/continuity layer, không nên đồng nhất hoàn toàn với từng provider execution lane
  - nguồn: <https://raw.githubusercontent.com/moeru-ai/airi/main/README.md>
  - nguồn: <https://vedal.ai/neuro-blog.html>

## Kết luận kiến trúc

### 1. `House voice` khác với `house provider`

Phát hiện quan trọng nhất của vòng audit này:

- nếu đồng nhất `house voice = house provider`, explicit `GLM-5` vẫn bị vòng qua Google trước
- khi Google đang quota/busy, direct lane bị mất thêm hàng chục giây vì retry/failover

Kiến trúc đúng hơn:

- `house voice / living identity` nằm ở prompt, conductor, narrator, routing style
- `execution provider` phải tôn trọng explicit pin của user
- chỉ `auto` mới được quyền cross-provider failover

### 2. Visible thinking phải đến sớm, không nhất thiết answer phải đến ngay

Sau patch, stream path hiện đã cho visible thinking xuất hiện rất sớm:

- `thinking_start / thinking_delta` đến trong khoảng `~0.2s → 1.8s`
- đây là cải thiện đúng tinh thần “Wiii đang sống và đang nghĩ”

### 3. Độ trễ còn lại chủ yếu nằm ở provider execution lane

Khi `provider=zhipu` / `glm-5`:

- supervisor vẫn là `LLM-first`
- visible thinking đến sớm
- nhưng direct/code_studio answer vẫn có thể mất `~20–40s`

Đây không còn là lỗi “đơ không stream”, mà là chi phí execution thực của provider/model đang phục vụ lane đó.

## Những gì đã sửa

### A. Direct lane tôn trọng explicit provider pin

File:

- `maritime-ai-service/app/engine/multi_agent/graph.py`

Sửa:

- giữ house voice ở prompt/lane
- nhưng explicit provider như `zhipu` vẫn được dùng đúng ở direct lane
- tránh vòng retry Google rồi mới failover sang Zhipu

### B. Visible thinking local bớt generic và gần Wiii hơn

File:

- `maritime-ai-service/app/engine/reasoning/reasoning_narrator.py`

Sửa:

- bỏ nhiều câu ASCII/generic kiểu kỹ thuật
- thêm phrasing gần nhịp Wiii hơn, nhất là social/off-topic/code_studio
- nhấn mạnh rằng turn ngắn vẫn có thể mang ẩn ý, không coi người dùng là “chỉ nói vu vơ”

### C. Sentiment nền bỏ bớt LLM call vô ích cho micro-banter

File:

- `maritime-ai-service/app/engine/living_agent/sentiment_analyzer.py`

Sửa:

- thêm fast-path rất bảo thủ cho micro-banter như `hehe`, `wow`, `gì đó`
- giảm cạnh tranh tài nguyên ở background sau khi đã trả lời xong
- không ảnh hưởng routing/visible thinking của lượt chính

### D. Fallback Code Studio nói tiếng Việt chuẩn hơn

File:

- `maritime-ai-service/app/engine/multi_agent/graph.py`

Sửa:

- clarifier/failure text cho simulation lane ấm hơn và tự nhiên hơn
- bỏ phrasing cứng hoặc dễ kéo trải nghiệm sang giọng “máy”

## Kiểm chứng

### Unit tests

- `test_graph_routing.py`
- `test_sprint210d_llm_sentiment.py`

Kết quả:

- `75 passed`

### Runtime truth hiện tại

`GET /api/v1/llm/status`

- `google`: `disabled / busy`
- `zhipu`: `selectable`
- `ollama`: `disabled / host_down`
- `openai/openrouter`: `hidden`

### Smoke stream thật sau patch

Provider: `zhipu`

- `he he`
  - first thinking: `~1.77s`
  - first answer: `~29.61s`
  - total: `~31.63s`
- `wow`
  - first thinking: `~0.49s`
  - first answer: `~20.97s`
  - total: `~22.67s`
- `gi do`
  - first thinking: `~0.25s`
  - first answer: `~31.01s`
  - total: `~31.25s`
- `mo phong duoc chu`
  - first thinking: `~0.54s`
  - first answer: `~40.74s`
  - total: `~40.84s`
  - routed correctly to `code_studio_agent`

## Diễn giải đúng

### Đã tốt hơn

- Wiii không còn “đứng hình rồi bỗng trả ra cả thinking lẫn answer cùng lúc” như trước
- visible thinking đến đủ sớm để người dùng thấy Wiii đang suy nghĩ thật
- house identity ổn hơn ở local narrator/fallback

### Chưa xong hẳn

- explicit `GLM-5` vẫn khá chậm ở answer lane
- đây là chi phí execution thực, không phải còn thiếu stream/thinking nữa
- nếu Google tiếp tục `busy`, “giọng chuẩn Gemini” cho general lane sẽ không phục hồi hoàn toàn ở runtime hiện tại

## Đề xuất phase sau

1. Giữ `LLM-first routing`, không mở rộng thêm keyword fast path.
2. Tách rõ hơn `house conductor` khỏi `execution model`, nhất là ở supervisor + synthesis.
3. Cho direct lane stream answer token thật từ provider khi có thể, thay vì đợi final response hoàn tất rồi mới bung answer.
4. Nếu muốn Wiii “sống” hơn nữa, đầu tư vào:
   - better supervisor prelude labels
   - streamable answer deltas cho direct/code_studio
   - richer continuity-aware thinking chunks, không chỉ summary một cục

## Verdict

- Kiến trúc hiện tại đã gần hơn với triết lý `AI sống`
- visible thinking đã đi đúng hướng
- nút thắt lớn còn lại là `execution latency` của provider đang active, không còn là “thinking không hiện” như trước
