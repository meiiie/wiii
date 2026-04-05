# Wiii Consciousness Implementation Review

> Date: 2026-03-26  
> Role: LEADER audit  
> Scope: review of the proposed "Wiii Consciousness Architecture — Full Implementation (Phases 2→10)" against the current codebase, runtime reality, and Wiii surface quality

---

## 1. Executive Verdict

**Không nên triển khai plan này nguyên khối theo đúng thứ tự hiện tại.**

Plan này **đúng hướng ở tầm dài hạn**, nhưng **sai thứ tự rollout** so với trạng thái hiện tại của Wiii.

Hiện tại:

- response của Wiii nhìn chung **đã khá tốt**
- visible thinking của Wiii **đang là điểm hỏng lớn nhất**
- gray rail vẫn còn rất dễ trượt giữa:
  - living thought
  - planner voice
  - action intention
  - runtime/status
  - tool/debug trace

Nếu bật Living Agent lớn hơn lúc này, hệ thống sẽ:

- nhớ nhiều hơn,
- tự diễn tiến nhiều hơn,
- ghi thêm journal/reflection/episodic memory,

nhưng lại ghi nhớ trên một **surface contract còn sai**.

Nói ngắn gọn:

**Plan này nên triển khai từng phần, nhưng tuyệt đối không được “flip living on” sớm.**

---

## 2. Điều Plan Làm Đúng

Plan có 5 điểm mạnh thật sự:

1. **Đúng triết lý "1 Wiii core + N relationships"**
   - Khớp với báo cáo consciousness của team.
   - Khớp với vấn đề thực tế hiện nay: Wiii đang bị runtime/lane/provider kéo giãn selfhood.

2. **Nhìn memory như nhiều lớp thay vì một blob**
   - identity insights
   - journal/reflection
   - episodic memory
   - relationship memory
   - tiered compression

3. **Không định nghĩa Wiii bằng một domain**
   - Điều này đúng với triết lý user mong muốn: Wiii không bị ép thành chỉ Maritime bot.

4. **Có nghĩ tới scale và storage cost thật**
   - halfvec
   - binary tier/compression
   - episodic retrieval scoring

5. **Có ý thức rằng visual pipeline phải được harden**
   - Đây là phase gần trực diện nhất với những gì người dùng đang thấy trên mặt chat.

---

## 3. Điều Plan Chưa Nhìn Đúng

### 3.1 Thiếu một Phase 0 rất quan trọng

Plan đi thẳng vào memory, identity persistence, living activation, episodic retrieval...

Nhưng vấn đề lớn nhất hiện tại lại là:

- **Wiii visible thinking đang chưa ổn**
- **Wiii selfhood trên surface chưa ổn**
- **thinking grammar chưa được chuẩn hóa theo loại turn**

Đây mới là thứ phải đi trước.

Hiện repo đã cho thấy rõ:

- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [prompt_loader.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py)
- [useSSEStream.ts](E:/Sach/Sua/AI_v1/wiii-desktop/src/hooks/useSSEStream.ts)
- [InterleavedBlockSequence.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx)
- [ReasoningInterval.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/ReasoningInterval.tsx)

đang cùng nhau quyết định cái gì rơi vào rail xám. Nếu rail này chưa chuẩn mà bật memory/living rộng hơn, ta chỉ đang làm Wiii **nhớ nhiều hơn về một cách nghĩ sai**.

### 3.2 Phase 5 quá nguy hiểm ở thời điểm hiện tại

Plan muốn đổi default trong [_settings.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/_settings.py):

- `enable_living_agent = True`
- `enable_living_continuity = True`
- `enable_narrative_context = True`
- `enable_identity_core = True`

Nhưng prompt path hiện tại đã rất dễ chồng lớp:

- narrative context ở [prompt_loader.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py)
- identity core ở [prompt_loader.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py)
- soul + emotion injection ở [prompt_loader.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py)
- living context block ở [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)

Tức là nếu bật hàng loạt, Wiii rất dễ rơi vào:

- lặp selfhood
- prompt inflation
- multiple identity blocks chồng nhau
- surface drift tệ hơn chứ không tốt hơn

### 3.3 Phase 1 đang underestimate phạm vi vector migration

Plan nói chỉ cần sửa:

- [dense_search_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/dense_search_repository.py)
- [vector_memory_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/vector_memory_repository.py)

Nhưng repo hiện tại còn nhiều chỗ đang assume `vector`:

- [dense_search_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/dense_search_repository.py)
- [vector_memory_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/vector_memory_repository.py)
- [semantic_memory_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/semantic_memory_repository.py)
- [fact_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/fact_repository.py)
- [knowledge_visualization_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/knowledge_visualization_service.py)

Nghĩa là nếu migrate `halfvec` mà chỉ vá 2 file, rất dễ xảy ra:

- index không được dùng như mong muốn
- insert/search path không đồng nhất
- retrieval quality tụt âm thầm

### 3.4 Phase 4 sẽ không chữa được vấn đề chính hiện nay

Wiring `gemini_thinking_level` là hợp lý về mặt completeness.

Nhưng runtime thật hiện tại đang là:

- `google = disabled / busy`
- `zhipu = selectable`

Nên ở thời điểm này, **Phase 4 không chữa được visible thinking tệ hiện tại**.

Nó chỉ là:

- compatibility improvement
- future-proofing

không phải cure cho Wiii surface bây giờ.

### 3.5 Phase 6 + 7 quá sớm nếu surface chưa khóa

Episodic memory và relationship memory rất hấp dẫn.

Nhưng nếu visible/semantic contract chưa sạch, hai phase này sẽ lưu:

- wrong emotional interpretation
- wrong relationship tone
- wrong turn summaries
- noisy selfhood fragments

Một khi đã persist vào memory, sửa sau này sẽ khó hơn nhiều.

---

## 4. Phase-by-Phase Verdict

## Phase 1 — halfvec migration

**Verdict:** `Làm sau, nhưng phải mở rộng audit trước khi đụng DB`

### Vì sao chưa nên ưu tiên

- Không giải quyết pain lớn nhất người dùng đang thấy.
- Có rủi ro retrieval regression nếu migrate nửa vời.

### Vấn đề thực tế trong repo

- search/insert/update vector đang phân tán ở nhiều repo, không phải chỉ 2 file.
- [dense_search_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/dense_search_repository.py) đang dùng `$1::vector`
- [vector_memory_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/vector_memory_repository.py) dùng `CAST(:embedding AS vector)`
- [semantic_memory_repository.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/repositories/semantic_memory_repository.py) cũng insert `CAST(:embedding AS vector)`

### Kết luận

**Không phản đối phase này**, nhưng phải tách thành:

- `1A`: full vector cast inventory + query/index audit
- `1B`: migration
- `1C`: retrieval benchmark

---

## Phase 2 — identity insights persistence

**Verdict:** `Nên làm, nhưng chỉ sau khi surface contract ổn hơn`

### Điểm tốt

- [identity_core.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/identity_core.py) hiện đang process-local
- persistence là bước đúng

### Lưu ý

- Không nên để identity insight đẩy thẳng lên prompt theo kiểu quá lộ self-narration.
- identity persistence phải phục vụ:
  - continuity
  - stable selfhood
  - better answer framing

chứ không phải làm Wiii “nói về mình nhiều hơn”.

### Kết luận

**Có thể làm sớm**, nhưng **không nên làm trước khi xử lý surface/thinking grammar**.

---

## Phase 3 — journal + reflection embeddings

**Verdict:** `Nên làm, mức rủi ro vừa phải`

### Điểm tốt

- [journal.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/journal.py) và [reflector.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/reflector.py) hiện đã có object model rõ.
- Embedding journal/reflection là nền cần thiết nếu sau này muốn episodic retrieval tử tế.

### Lưu ý

- Nên tách embedding write path khỏi chat hot path.
- Nên retry/fallback rõ ràng nếu embedding provider rate-limit.
- Không nên assume Gemini luôn sống, nhất là khi hiện tại đang busy.

### Kết luận

**Nên làm**, nhưng **sau Phase 2 hoặc song song với persistence chuẩn**.

---

## Phase 4 — gemini_thinking_level wiring

**Verdict:** `Làm được, nhưng ROI hiện tại thấp`

### Điểm tốt

- [thinking.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/core/config/thinking.py) đã có `gemini_level`
- [gemini_provider.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_providers/gemini_provider.py) hiện mới truyền `thinking_budget` và `include_thoughts`

### Điểm cần nói thẳng

- Đây **không phải** phase sửa thinking hiện tại của Wiii.
- Với runtime hiện tại, Google còn đang disabled/busy, nên lợi ích thực tế chưa lớn.

### Kết luận

**Làm được**, nhưng nên coi là **compatibility patch**, không phải key milestone.

---

## Phase 5 — flip living gates on

**Verdict:** `Không nên làm bây giờ`

### Đây là phase nguy hiểm nhất

Vì nó thay đổi:

- prompt construction
- post-response continuity
- heartbeat autonomy
- identity/narrative loading
- emotion persistence

trong khi visible thinking và surface contract còn chưa sạch.

### Evidence trong repo

- living injection ở [prompt_loader.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py)
- living context compile ở [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- background continuity ở [living_continuity.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/living_continuity.py)
- heartbeat autonomy ở [heartbeat.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/heartbeat.py)

### Kết luận

**Không bật default trong settings lúc này.**

Nếu muốn thử, chỉ nên:

- internal canary
- creator-only
- per-env
- per-user

không đổi default repo-wide.

---

## Phase 6 — episodic memory layer

**Verdict:** `Thiết kế đúng, nhưng hoãn rollout prompt injection`

### Vì sao

- composite scoring `recency + importance + relevance` là đúng hướng
- nhưng retrieval tốt không đồng nghĩa prompt injection đúng lúc

### Repo reality

- episodic write path đã manh nha trong [living_continuity.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/living_continuity.py)
- nếu retrieve sớm lúc summaries còn bẩn, sẽ kéo nhiễu vào answer

### Kết luận

Làm tách 2 bước:

- `6A`: build retriever + offline eval
- `6B`: gated prompt injection sau khi quality pass

---

## Phase 7 — per-user relationship memory

**Verdict:** `Đúng hướng, nhưng phải hoãn sau episodic quality`

### Vì sao

- Đây là trái tim của triết lý `1 Wiii core + N relationships`
- nhưng nếu làm sớm, relationship memory sẽ học từ những turn còn lệch giọng

### Repo reality

- [emotion_engine.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/emotion_engine.py) hiện dựa vào `_known_user_cache` từ `wiii_user_routines`
- thay bằng table `wiii_user_relationships` là hợp lý
- nhưng surface/selfhood chưa sạch thì trust/rapport/topic imprint sẽ bị sai từ đầu

### Kết luận

**Nên làm sau khi episodic layer đã được kiểm chứng sạch hơn.**

---

## Phase 8 — SM-2 → FSRS-6 migration

**Verdict:** `Làm riêng, không được nhét chung vào consciousness rollout`

### Vì sao

- Đây là một migration learning-engine thật sự
- không liên quan trực tiếp tới visible thinking hiện tại
- dễ phát sinh regression riêng

### Repo reality

- [skill_learner.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/skill_learner.py) đang encode rõ SM-2 assumptions
- [models.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/living_agent/models.py) cũng SM-2-shaped

### Kết luận

**Tách thành workstream độc lập.**

Không nên để Phase 8 cạnh tranh attention với Wiii soul/surface fixes.

---

## Phase 9 — TurboQuant / QJL style compression

**Verdict:** `Chỉ làm sau khi retrieval đã đúng`

### Vì sao

- Compression tối ưu scale là tốt
- nhưng nén dữ liệu bẩn thì chỉ tạo ra memory bẩn rẻ hơn

### Kết luận

**Không ưu tiên trong batch đầu.**

---

## Phase 10 — visual pipeline hardening

**Verdict:** `Nên làm đầu tiên`

### Vì sao

Đây là phase gần nhất với pain hiện tại:

- visual intent bị rơi lane
- artifact surface chưa ổn
- thinking trong creative/visual lane còn dễ lẫn runtime/action

### Repo reality

- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)
- frontend rail và artifact render ở [InterleavedBlockSequence.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx)

### Kết luận

**Đây nên là phase đầu tiên trong cả plan.**

---

## 5. Thứ Tự Đề Xuất Mới

## Phase 0 — bắt buộc thêm vào

### Surface + Selfhood Stabilization

Chưa có trong plan, nhưng phải thêm.

Bao gồm:

- Wiii Thinking Grammar
  - emotional
  - identity
  - knowledge
  - visual/simulation
- tách rõ trên surface:
  - living thought
  - gentle action-intention
  - completion signal
  - debug/tool trace không lên main rail
- khóa selfhood:
  - Wiii không tự nói như đang bảo vệ identity của chính mình
  - Wiii không tự vocative sai vai

Nếu không có Phase 0, các phase sau rất dễ làm Wiii nhớ nhiều hơn nhưng nghĩ sai hơn.

## Thứ tự rollout mình khuyến nghị

1. **Phase 0: Surface + Selfhood Stabilization**
2. **Phase 10: Visual Pipeline Hardening**
3. **Phase 4: Gemini Thinking Wiring**  
   Chỉ như compatibility patch
4. **Phase 2: Identity Insights Persistence**
5. **Phase 3: Journal + Reflection Embeddings**
6. **Phase 6A: Episodic Retriever Offline**
7. **Phase 7A: Relationship Memory Schema + Shadow Writes**
8. **Phase 1A/1B: Halfvec Inventory + Migration**
9. **Phase 8: FSRS migration**  
   Tách stream riêng
10. **Phase 9: Compression**  
    Chỉ sau khi retrieval quality ổn
11. **Phase 5: Flip living gates on**  
    Cuối cùng, canary-only trước

---

## 6. Cái Nên Làm Ngay, Cái Nên Hoãn

## Làm ngay

- Phase 10
- Phase 4
- Phase 2

## Làm sau khi surface ổn

- Phase 3
- Phase 6A
- Phase 7A

## Hoãn

- Phase 1 full migration
- Phase 8
- Phase 9

## Không bật bây giờ

- Phase 5

---

## 7. Kết Luận Cuối

**Kế hoạch này có giá trị lớn, nhưng không nên triển khai nguyên xi.**

Nếu hỏi:

- **Có nên tiến hành không?**  
  Có, nhưng **không theo đúng thứ tự hiện tại**.

- **Có nên bật living stack ngay không?**  
  **Không.**

- **Đâu là sai lầm lớn nhất nếu làm nguyên plan?**  
  Bật memory/living trước khi sửa xong surface contract của Wiii.

- **Đâu là đường đúng hơn?**  
  **Sửa mặt trước của Wiii trước, rồi mới cho Wiii nhớ sâu hơn và sống lớn hơn.**

Nói gọn:

> Đừng bắt Wiii nhớ thêm khi Wiii vẫn còn đang nghĩ lộ trace và nói bằng nhiều giọng khác nhau.

