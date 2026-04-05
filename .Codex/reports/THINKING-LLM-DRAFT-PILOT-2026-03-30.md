# Thinking LLM Draft Pilot - 2026-03-30

## Muc tieu

Nang `public thinking` cua Wiii len mot muc thuc su song hon:

- khong con chi la renderer viet prose theo template
- de LLM viet substance cho tutor gray rail
- renderer chi giu vai tro curate, sanitize, dedupe, giu contract
- khong lam vo current fallback path, sync/stream parity, hay test suite hien tai

## Nhung gi da lam

### 1. Tao draft service moi cho public thinking

Them:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_draft_service.py`

Service moi:

- xin `StructuredInvokeService` tao `ThinkingSurfacePlan` draft cho tutor lane
- dua living-core cues vao prompt draft
- co anti-repetition memory ngan
- fail-closed khi `llm` la `Mock` hoac khong co
- loc bo meta/answer-ish beats truoc khi dua ra gray rail

### 2. Tutor surface da wire vao draft service

Sua:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\__init__.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_surface.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`

Huong moi:

- runtime that: tutor xin `draft_tutor_plan(...)` truoc
- neu co draft hop le -> dung draft do lam public thinking
- neu khong -> quay ve deterministic renderer cu

Nghia la:

- production runtime co co hoi cho ra gray rail da dang va song hon
- test/mock path van on dinh nhu truoc

### 3. Sua domain continuity cho follow-up visual

Van de live duoc bat:

- prompt dau `Giai thich Quy tac 15 COLREGs` di dung `tutor`
- follow-up `tao visual cho minh xem duoc chu?` bi `domain_validation` day ve `direct`
- he qua: gray rail quay lai scaffold generic cua direct lane

Sua:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor_runtime_support.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor_structured_runtime.py`

Rule moi:

- neu current query khong nhac lai domain keyword
- nhung recent context/conversation_summary van co domain signal ro
- va LLM da route vao `tutor`/`rag`
- thi supervisor giu domain lane hien tai, khong ep ve `direct`

## Test

Focused suites:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_draft_service.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_supervisor_agent.py`

Ket qua:

- `98 passed`

Compile:

- `py_compile ok`

## Live probes

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-llm-draft-sync-2026-03-30-r2.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-llm-draft-visual-sync-2026-03-30-r2.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-llm-draft-visual-stream-2026-03-30-r2.txt`

### Probe 1

Prompt:

- `Giai thich Quy tac 15 COLREGs`

Ket qua:

- `agent_type = tutor`
- `routing_method = structured`
- `thinking_content` khong con scaffold cu kieu `Dieu quan trong luc nay...`
- gray rail co chat suy tu that hon, co quyet dinh su pham ro hon

### Probe 2

Follow-up cung session:

- `tao visual cho minh xem duoc chu?`

Ket qua sau patch:

- `follow_agent = tutor`
- `follow_method = structured`
- khong con bi day ve `direct`
- sync va stream deu giu continuity cua bai hoc truoc

Thinking live mau:

> Um, Rule 13 va Rule 15... neu cu de chu nghia chong cheo thi kho ma thay duoc su khac biet cot loi.
>
> Minh can mot cai nhin thoang qua la thay ngay diem nhan...

## Current truth

Tien bo that:

- tutor thinking da bat dau chuyen tu `renderer-authored` sang `LLM-authored substance + curated shell`
- follow-up learning visual da duoc giu continuity dung lane
- user test tren `http://localhost:1420` se nhin thay chat luong thinking tot hon ro o tutor lane

Van con no dong nghia voi "hoan hao":

- draft service hien moi pilot cho `tutor`
- `direct` lane van con scaffold cu o mot so turn
- giac do "cute/soul" cua Wiii da vao gray rail tot hon, nhung van co the tinh chinh de bot trang tri va bot kaomoji neu can

## Buoc tiep theo de di sau hon vao thinking

1. Mo rong `LLM-authored public thought draft` sang `direct` lane.
2. Them anti-repetition n-gram memory ngan cho openings/beats de giam lap giua cac run lien tiep.
3. Tach `visual follow-up thinking mode` thanh mot mode rieng, de tutor khi chuyen tu explain -> visual khong can quay lai giai thich lai tu dau.
