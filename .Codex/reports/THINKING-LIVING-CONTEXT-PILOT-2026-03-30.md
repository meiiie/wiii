# THINKING LIVING CONTEXT PILOT — 2026-03-30

## Muc tieu

Noi public thinking vao cung mot backbone song voi Wiii thay vi chi tone-shaping theo tung lane.

Phase nay tap trung vao:

- tao `LivingThinkingContext`
- wire `memory` vao backbone moi
- wire `tutor` vao backbone moi o ca stream va sync
- khoa contract bang focused tests va live probes

## Files da sua

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\living_thinking_context.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\__init__.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\memory_agent.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_surface.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_memory_agent_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`

## Kien truc moi

### 1. `LivingThinkingContext`

Module moi rut public-facing cues tu runtime character backbone:

- character card summary
- identity anchor
- voice tone
- expressive language
- relationship style
- reasoning style
- `personality_mode`
- `mood_hint`

Va quy doi thanh `soul_intensity` theo lane:

- `memory`, `direct`, `personal`, `social` -> `LIVING`
- `tutor`, `learning`, `lookup` -> `BALANCED`
- `rag`, `tool`, `retrieval` -> `RESTRAINED`

### 2. Renderer trung tam

`apply_living_thinking_context(...)` duoc them vao `public_thinking_renderer.py`.

No khong de tung lane tu viet prose tuy hung. Thay vao do:

- clone `ThinkingSurfacePlan`
- them `strategy` beat co kiem soat
- chi inject vao lane/phase duoc phep
- giu summary la meta, body la public reasoning

### 3. Memory lane

`memory_agent.py` gio build `LivingThinkingContext` ngay dau turn va apply vao:

- `retrieve`
- `existing`
- `extract`
- `new_fact`
- `synthesize`

Ket qua la gray rail memory khong chi sach leak, ma con bat dau mang y niem:

- nho that
- hien dien lien mach
- khong bien response thanh nhat ky he thong

### 4. Tutor lane

`tutor_surface.py` gio co:

- `_build_tutor_living_thinking_context(context)`
- `build_sync_tutor_public_thinking(...)`

Va `tutor_node.py` gio prepend sync thinking bang curated tutor public plan khi native/private thinking khong hop le.

Y nghia:

- stream va sync khong con tach hai su that khac nhau cho tutor thinking
- private llm thinking co the bi drop, nhung sync van co living-safe gray rail

## Focused verification

### Compile

`python -m py_compile` pass cho toan bo file moi/chinh.

### Tests

Chay:

```powershell
python -m pytest tests/unit/test_public_thinking_renderer.py tests/unit/test_memory_agent_node.py tests/unit/test_tutor_agent_node.py -q -p no:capture
```

Ket qua:

- `57 passed`

## Live verification

Backend sau restart:

- `http://localhost:8000/api/v1/health/live` -> `{"status":"alive"}`

Frontend local:

- `http://localhost:1420` khong dang chay trong session nay

### Artifact probes

- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-memory-sync-2026-03-30-r3.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-sync-2026-03-30-r3.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r3.txt`

### Memory live truth

Prompt:

`Mình tên Nam, nhớ giúp mình nhé.`

Sync `thinking_content` da mang continuity strategy moi, tieu bieu:

- `...mình nhớ thật và vẫn hiện diện liền mạch...`
- `...không biến phản hồi thành nhật ký hệ thống.`

Memory answer sync cung dung lane:

- `Wiii đã ghi nhớ bạn tên là Nam rồi nè!...`

Luu y:

- probe memory cu hon (`r2`) bi nhieu do reuse thread/user qua mo, nen `r3` la moc dang tin hon.

### Tutor live truth

Prompt probe dung:

`Giải thích sự khác nhau giữa COLREGs Rule 13 và Rule 15 trong hàng hải.`

Va gui kem:

- `domain_id = maritime`
- `session_id` rieng trong body

#### Stream

Tutor stream da di qua living backbone dung cach:

- header `thinking_start` mang summary instructional, khong bi greeting
- body co curated beats:
  - `Minh nen giu phan trinh bay xoay quanh mot tieu chi chinh truoc...`
  - `Gio minh can goi ra dung ranh gioi giua Rule 13 va Rule 15 tu nguon...`

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r3.txt`

#### Sync

Tutor sync `thinking_content` da dung backbone moi va khop huong voi stream:

- `Cau mo dau phai chot ngay mau chot...`
- `Minh se giu giong than thien nhung khong vo ve...`
- `Nhip gan gui cua Wiii o day phai nam o cach go roi cho nguoi hoc...`
- `Gio minh can goi ra dung ranh gioi giua Rule 13 va Rule 15 tu nguon...`

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-sync-2026-03-30-r3.json`

## Van de con lai

### 1. Tutor sync answer chua on dinh

Trong probe `r3`, tutor sync answer van co the roi vao placeholder sai:

- `**Generating a Placeholder** ...`

Trong khi tutor stream cung prompt lai ra answer dung lane va dung noi dung.

=> Day khong con la bug thinking authority.
=> Day la bug o tutor answer generation / sync parity / fallback selection.

### 2. Routing can ro domain hon o prompt mo ho

Prompt mo ho kieu:

- `Giải thích Rule 15 khác gì Rule 13?`

co the bi route ve `direct/off_topic` va dien giai theo internet meme neu khong co:

- `domain_id = maritime`
- hoac context/prompt ne ro `COLREGs`, `trong hàng hải`

Dieu nay giai thich vi sao tutor live probe cu bi lech lane.

### 3. `.Codex/agents` khong ton tai trong workspace

`AGENTS.md` tham chieu:

- `.Codex/agents/leader.md`

nhung workspace hien tai khong co folder nay. Khong chan implementation, nhung team nen biet de tranh ky vong co persona-file local.

## Danh gia

Pilot nay thanh cong o 3 diem:

1. `memory` gray rail da bat dau co soul theo kieu living-core, khong chi procedural.
2. `tutor` sync/stream public thinking da duoc gom ve chung mot subsystem.
3. Contract test da cap nhat theo he moi: cho phep curated living-plan, cam private-thought leak.

## Bước tiếp theo nen lam

P1 tiep theo hop ly nhat:

1. sua `tutor sync answer parity`
2. tach `living answer policy` khoi `thinking policy`
3. sau do moi mo rong `LivingThinkingContext` sang `direct` lane

Neu sua tiep, file co ROI cao nhat:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_response.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\rag_tools.py`
