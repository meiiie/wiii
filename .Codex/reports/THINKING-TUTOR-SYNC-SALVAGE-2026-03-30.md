# Thinking Tutor Sync Salvage - 2026-03-30

## Muc tieu

Khoa lai tutor learning lane sau khi da dua `thinking` ve dung authority/living backbone:

- sync khong duoc roi ve placeholder `"Xin loi..."` neu tool result cuoi van tot
- stream va sync cung phai giu thesis-first
- tutor answer khong chen greeting/opener hoac kaomoji trang tri vao giua doan giang giai

## Root Cause

Sau patch `LivingThinkingContext`, tutor lane van co mot split xau:

- stream `/api/v1/chat/stream/v3` thuong cho answer dung
- sync `/api/v1/chat` co the synthesize ra placeholder ngan (~56 chars)

Log live xac nhan:

- tutor thinking van duoc tao dung va CRAG/tool flow van thanh cong
- nhung nhat `final generation` cua sync co the tu sut xuong placeholder
- khi do ca turn bi keo xuong, du `tool_knowledge_search` vua tra ve mot cau tra loi dung

Van de that khong con nam o presenter hay transport, ma nam o `TutorAgentNode._react_loop()` sau tool rounds.

## Files Changed

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_response.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_response.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`

## What Changed

### 1. Tutor placeholder detection

Them `looks_like_tutor_placeholder_answer(...)` de nhan ra cac final answer kieu:

- `"Xin loi..."`
- `"co gi do truc trac..."`
- placeholder ngan/vo nghia sau final generation

### 2. Tool-result salvage

Them `recover_tutor_answer_from_messages(...)`:

- duyet nguoc `ToolMessage` moi nhat
- bo `<!-- CONFIDENCE ... -->`
- bo tool error
- normalize lai bang `normalize_tutor_answer_shape(...)`
- ep thesis-first neu day la compare query

Neu final answer bi placeholder nhung `tools_used` da co ket qua tot, tutor se lay lai cau tra loi tu tool observation cuoi.

### 3. Decorative aside cleanup

Them strip cho parenthetical trang tri kieu kaomoji:

- vi du `(˶˃ ᵕ ˂˶)`

Tutor learning answer giu warmth bang nhip cau, khong chen marker cute vao giua doan giang giai.

## Tests

Focused suite:

- `python -m pytest tests/unit/test_tutor_response.py tests/unit/test_tutor_agent_node.py -q -p no:capture`

Ket qua:

- `37 passed`

Co them 2 regression tests quan trong:

- strip repeat-question / greeting / decorative opener
- recover answer tu tool result khi final generation bi placeholder

## Live Verify

Artifacts:

- sync: `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-sync-2026-03-30-r9.json`
- stream: `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r9.json`

Current truth:

- sync: `200`, khong con `"Xin loi..."`, khong con kaomoji trang tri
- stream: `200`, answer mo thesis-first, khong placeholder, khong kaomoji
- gray rail van giu living tutor thinking:
  - chot mau chot truoc
  - giu giong than thien nhung khong vo ve
  - warmth nam o cach go roi cho nguoi hoc, khong o man chao hoi

Log live xac nhan:

- `Recovered tutor answer from tool observation after placeholder final generation`
- sync final response da tang tu `56` chars placeholder len response that su

## Verdict

Tutor lane da tot hon ro o 3 diem:

1. `thinking` van co soul va dung lane
2. sync khong con sut ve placeholder vo nghia sau tool rounds
3. answer da giu thesis-first ky luat hon ma khong danh mat Wiii warmth

## Next Best Step

Van con mot khac biet nhe:

- sync hien tai van dung tool-result salvage nhieu hon stream
- stream van co the sinh answer dai hon va tu nhien hon trong mot so run

Bac tiep theo hop ly nhat:

- dua tutor `post-tool final synthesis` thanh mot contract/surface chung cho ca sync va stream
- khi do khong chi salvage sau loi, ma ca hai transport se dung cung mot answer-shaping path tu dau
