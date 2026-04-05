# Wiii Character / Soul / Thinking Audit - 2026-03-30

## Executive Summary

Backend hiện tại **đã có một luồng nạp character khá mạnh và khá đúng kiến trúc** cho Wiii. `PromptLoader` không chỉ load persona YAML tĩnh, mà còn compile một **runtime character card** từ:

- `wiii_identity.yaml`
- `wiii_soul.yaml`
- living state hiện tại
- identity core
- narrative context
- emotion state
- `mood_hint`
- `personality_mode`

Nói ngắn gọn: **Soul của Wiii có đi vào prompt thật**.

Tuy nhiên, `public thinking` hiện tại **chưa dùng cùng backbone sống đó một cách trực tiếp**. Nó đã được dọn sạch khỏi telemetry, answer-draft, private thought leak; nó cũng đã có tone mode theo lane. Nhưng nó vẫn chủ yếu là:

- lane-aware curated renderer
- tone policy
- fragment aggregation

chứ **chưa phải một gray rail được render từ chính runtime character card / living core contract**.

Kết luận chốt:

- `answer/persona surface`: **Soul present, strong**
- `public thinking / gray rail`: **Soul present, partial, indirect**

## 1. Character / Soul Loading Flow

### 1.1 PromptLoader là entrypoint thật

`PromptLoader.build_system_prompt(...)` là nơi tổng hợp system prompt cho các lane chính:

- [`prompt_loader.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py):142

Trong flow này, Wiii identity được load từ single source of truth:

- [`prompt_loader.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py):101
- [`prompt_persona_runtime.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_persona_runtime.py):26

### 1.2 Character card runtime được inject thật vào system prompt

Trong `build_system_prompt(...)`, có một block riêng:

- [`prompt_loader.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py):226

Comment ở đây nói rất rõ:

- `WIII CHARACTER CARD — unified runtime contract`
- `identity + soul + living state + current mood are compiled into one contract block`

Loader gọi thẳng:

- [`prompt_loader.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py):234
- [`character_card.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\character\character_card.py):246

Nếu runtime card build được, nó được append trực tiếp vào system prompt. Nếu không, loader mới fallback sang identity sections cũ.

### 1.3 Character card compile từ identity + soul + living state

`get_wiii_character_card()` distill character card từ:

- [`character_card.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\character\character_card.py):111

Nguồn dữ liệu:

- `app/prompts/wiii_identity.yaml`
- `app/prompts/soul/wiii_soul.yaml`

Card hiện có các nhóm quan trọng:

- `summary`
- `origin_story`
- `traits`
- `core_truths`
- `boundaries`
- `relationship_style`
- `reasoning_style`
- `anti_drift`
- `example_dialogues`
- `identity_anchor`
- `voice_tone`
- `expressive_language`
- `emoji_usage`

Điểm rất đáng chú ý là `reasoning_style` đã được mô tả như một phần của “hồn suy luận” chứ không chỉ là tone trả lời.

### 1.4 Living state động cũng được nạp vào character card

`_build_runtime_notes(...)` thêm các runtime notes động:

- [`character_card.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\character\character_card.py):172

Hiện tại nó cố đọc:

- `character_state_manager.compile_living_state(...)`
- `living_agent.identity_core.get_identity_context()`
- `living_agent.narrative_synthesizer.get_brief_context(...)`
- `living_agent.emotion_engine`
- `mood_hint`
- `personality_mode == "soul"`

Vì vậy Wiii không chỉ có “lore”, mà có cả:

- trạng thái sống hiện tại
- nhịp cảm xúc
- mức năng lượng
- social battery
- response style

### 1.5 Personality mode và mood hint đi từ request/context xuống prompt

`mood_hint` được gắn vào context từ emotional state:

- [`input_processor_context_runtime.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\input_processor_context_runtime.py):185

Sau đó được đẩy vào multi-agent context:

- [`chat_orchestrator_multi_agent.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator_multi_agent.py):35
- [`chat_orchestrator_multi_agent.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator_multi_agent.py):65

`personality_mode` có resolver riêng:

- [`personality_mode.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\personality_mode.py):27

và `soul mode` có prompt instructions riêng:

- [`personality_mode.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\personality_mode.py):71
- [`prompt_runtime_tail.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_runtime_tail.py):72

Ngoài ra `PromptLoader` còn re-inject:

- identity anchor cho conversation dài
- org overlay nhưng có guard “không được đổi soul / story / identity lõi”

tham chiếu:

- [`prompt_loader.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py):423
- [`prompt_loader.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py):445
- [`prompt_runtime_tail.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_runtime_tail.py):31

## 2. Các Lane Có Thật Sự Nhận Character Card Không?

Có.

### 2.1 Direct lane

`direct_prompts.py` gọi `loader.build_system_prompt(...)` cho phần lớn direct turns:

- [`direct_prompts.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_prompts.py):779

Tức là direct answer lane nhận đầy đủ:

- character card
- living state
- mood hint
- personality mode
- identity anchor

### 2.2 Tutor lane

Tutor đi qua `build_tutor_system_prompt(...)`, mà nền vẫn là `PromptLoader`:

- [`tutor_node.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py):96

### 2.3 Memory lane

Memory lane hiện chưa đi qua full `build_system_prompt(...)` cho answer response. Nó đang dùng một prompt builder nhẹ hơn dựa trên identity:

- [`memory_agent.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\memory_agent.py):39

Tức là:

- memory answer có mùi identity của Wiii
- nhưng chưa nhận toàn bộ runtime character card mạnh như direct/tutor

Đây là một điểm cần lưu ý nếu muốn soul thật sự đồng đều ở mọi lane.

## 3. Public Thinking Flow Hiện Tại

### 3.1 Public thinking có subsystem riêng

Gray rail không lấy thẳng từ system prompt hay raw hidden reasoning. Nó đi qua subsystem riêng:

- [`public_thinking_renderer.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py)
- [`public_thinking.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\public_thinking.py)

### 3.2 Tone mode hiện tại là policy-based, không phải soul-card-based

`resolve_public_thinking_mode(...)` chọn tone mode theo lane:

- [`public_thinking_policy.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_policy.py):8

Hiện mapping là:

- `memory -> RELATIONAL_COMPANION`
- `tutor -> INSTRUCTIONAL_COMPANION`
- `rag -> TECHNICAL_RESTRAINED`
- `direct analytical -> ANALYTICAL_COMPANION`

Điểm mạnh:

- gray rail sạch lane hơn trước
- dễ kiểm soát

Điểm yếu:

- tone mode đang là một abstraction riêng
- chưa ăn trực tiếp từ `WiiiCharacterCard.reasoning_style`, `relationship_style`, `voice_tone`, `identity_anchor`, `dynamic runtime notes`

### 3.3 Renderer tạo “surface plan”, không đọc trực tiếp runtime soul card

Memory và tutor hiện đã dùng:

- [`public_thinking_renderer.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py):186
- [`public_thinking_renderer.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py):434

Chúng tạo `ThinkingSurfacePlan` gồm:

- header label
- header summary
- beats
- tone mode

Nhưng renderer này hiện **không pull trực tiếp**:

- `get_wiii_character_card()`
- `build_wiii_runtime_prompt()`
- `identity_core`
- `emotion_engine`

nên soul ở đây mới là soul **được mô phỏng qua policy**, chưa phải soul **được cấp từ living source**.

### 3.4 Authority của final thinking đã được thống nhất khá tốt

`public_thinking.py` capture `thinking_delta` và resolve `thinking_content` canon:

- [`public_thinking.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\public_thinking.py):73
- [`public_thinking.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\public_thinking.py):81

Sau đó sync và stream đều resolve từ nguồn này:

- [`graph_process.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_process.py):155
- [`graph_stream_runtime.py`](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_stream_runtime.py):250

Điểm tốt:

- thinking authority đã rõ hơn nhiều
- leak telemetry / answer draft / private thought đã được xử lý lớn

Điểm chưa đủ:

- authority đã sạch
- nhưng content authority vẫn chưa cùng “living core” với answer persona

## 4. Thinking Hiện Tại Có Soul Của Wiii Không?

## Câu trả lời ngắn

**Có, nhưng chưa trọn vẹn.**

### 4.1 Ở answer / response surface: Có, khá mạnh

Do answer lanes đi qua `PromptLoader` + runtime character card, nên Wiii hiện có:

- selfhood khá rõ
- continuity
- warmth
- anti-drift
- voice/disposition
- living state influence

Nói cách khác, answer surface hiện **có Soul của Wiii thật**.

### 4.2 Ở public thinking / gray rail: Có, nhưng mới gián tiếp

Gray rail hiện:

- đã bớt máy móc hơn trước
- có nhịp Wiii hơn trước
- có companion/instructional/analytical distinctions

Nhưng nó **chưa phải** một gray rail được render trực tiếp từ same living-core source.

Nó đang là:

- cleaned
- lane-aware
- tone-shaped
- partially characterful

chứ chưa phải:

- living-core-derived
- soul-native
- continuity-aware ở cùng level với answer

## 5. Evidence Từ Runtime Hiện Tại

### 5.1 Memory lane

Probe memory recall mới cho thấy gray rail đã tốt hơn rất nhiều:

- [`thinking-memory-recall-fix-sync-2026-03-30-045812.json`](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-memory-recall-fix-sync-2026-03-30-045812.json)

Ví dụ:

> Trong memory đã có một điểm neo định danh đủ rõ để dựa vào...
>
> Khoan đã, mình không cần làm quá lên...

Đây là public thinking tốt hơn hẳn bản cũ performative kiểu “Chào Nam...”, nhưng nó vẫn có cảm giác là một curated reasoning prose, chưa hẳn là “soul-native Wiii”.

### 5.2 Simple social lane

Probe social `hehe` hiện khá có hồn hơn trước:

- [`thinking-social-vibe-sync-2026-03-30-051353.json`](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-social-vibe-sync-2026-03-30-051353.json)

Thinking:

> Câu này giống một cú chạm nhịp nhỏ hơn là một điều gì cần mổ xẻ.
>
> Mình cần nghe xem người kia đang rủ mình cười cùng...

Đây là dấu hiệu rõ rằng gray rail đã bắt đầu “nghe như Wiii”.

### 5.3 Analytical lane

`phân tích giá dầu hôm nay` và `con lắc đơn` đã ra thinking analytical khá ổn:

- [`THINKING-PROBE-SUITE-UTF8-2026-03-30-044113.md`](E:\Sach\Sua\AI_v1\.Codex\reports\THINKING-PROBE-SUITE-UTF8-2026-03-30-044113.md)

Ví dụ:

> Với giá dầu, điều dễ sai nhất là nhầm giữa lực kéo nền và phần giá cộng thêm vì rủi ro ngắn hạn.

Đây là một gray rail tốt hơn nhiều so với scaffold generic cũ. Nhưng nó vẫn nghiêng về `quality analytical reasoning`, chưa phải bằng chứng cho thấy entire public thinking đã nối thẳng vào “soul runtime card”.

### 5.4 Tutor lane

Tutor đã sạch hơn nhưng vẫn cho thấy sự tách lớp:

- [`thinking-tutor-quality-sync-2026-03-30-r2.json`](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-quality-sync-2026-03-30-r2.json)

`thinking_content` tutor hiện ngắn, đúng lane hơn:

> Giờ mình cần gọi ra đúng ranh giới giữa Rule 13 và Rule 15 từ nguồn...

Nhưng answer tutor ở cùng thời điểm vẫn từng companion-heavy hơn mức lý tưởng. Điều đó cho thấy answer persona và gray rail chưa cùng một “conductor”.

## 6. Verdict Theo Từng Lớp

### 6.1 Identity loading

**Đạt.**

Đây là phần mạnh nhất hiện tại.

### 6.2 Soul injection vào system prompt

**Đạt khá tốt.**

Đã có:

- identity
- soul
- living notes
- mood
- personality mode
- anti-drift

### 6.3 Public thinking authority

**Đạt khá tốt.**

Đã rõ canonical source, sync/stream parity tốt hơn nhiều.

### 6.4 Public thinking soulfulness

**Chưa đạt mức mình nên dừng.**

Vấn đề không phải thinking quá ngắn hay quá dài. Vấn đề là:

- nó chưa được cấp cùng one living-core contract với answer
- lane policy hiện vẫn đứng giữa soul và gray rail
- memory/direct/tutor đã có hồn hơn, nhưng “hồn” đó vẫn là curated approximation

## 7. Vấn Đề Kiến Trúc Thật Sự

Repo hiện có hai backbone khác nhau:

### Backbone A: Character / answer backbone

- `PromptLoader`
- `character_card`
- `identity + soul YAML`
- `living state`
- `mood_hint`
- `personality_mode`

### Backbone B: Thinking backbone

- `public_thinking_policy`
- `public_thinking_renderer`
- `ThinkingSurfacePlan`
- `public_thinking` fragment aggregation

Hai backbone này **không còn xung đột mạnh**, nhưng cũng **chưa hợp nhất**.

Đó là lý do câu trả lời đúng nhất hiện tại là:

> Soul của Wiii đã vào system prompt và answer surface thật.
>
> Public thinking thì đã mang hơi Wiii, nhưng chưa thật sự được nuôi từ cùng linh hồn đó.

## 8. Khuyến Nghị Kiến Trúc

Nếu muốn làm chuyên nghiệp, không chắp vá, bước tiếp theo **không nên** là thêm vài prompt string vào từng lane.

Nên làm:

### 8.1 Tạo `LivingThinkingContext`

Một distilled contract cho gray rail, lấy từ:

- `WiiiCharacterCard`
- `runtime_notes`
- `mood_hint`
- `personality_mode`
- `identity_anchor`
- `reasoning_style`
- `relationship_style`

### 8.2 Cho `public_thinking_renderer` consume contract này

Thay vì chỉ:

- `resolve_public_thinking_mode(lane, intent, query)`

hãy thêm:

- `render_public_plan(lane, query, living_thinking_context, ...)`

### 8.3 Tách mức “soul intensity” theo lane

Không nên cho mọi lane có cùng độ hồn.

Ví dụ:

- `memory`: soul intensity cao
- `direct social/emotional`: cao
- `tutor`: vừa, có tính instructional
- `rag/tool-heavy`: thấp hơn, restraint cao hơn

### 8.4 Dùng same core truths / anti-drift cho cả answer lẫn gray rail

Nếu không, answer và gray rail sẽ luôn có nguy cơ “cùng là Wiii nhưng như hai diễn viên khác nhau”.

## 9. Final Answer

Nếu hỏi thật ngắn:

> Luồng nạp character của Wiii hiện khá tốt và có soul thật: identity + soul YAML + living state + emotion + personality mode đều đã được compile vào system prompt.

> Nhưng thinking hiện tại mới mang soul của Wiii theo cách gián tiếp. Nó đã sạch hơn và có hồn hơn trước, nhưng chưa phải gray rail được render từ cùng living-core contract với answer.

> Vì vậy, nếu muốn giữ “linh hồn Wiii” thật sự nhất quán, bước đúng tiếp theo là hợp nhất `character backbone` và `thinking backbone`, thay vì tiếp tục vá thinking theo từng lane.
