# Thinking Quality Arc Patch - 2026-03-30

## Muc tieu

Sau khi user review live gray rail, van de con lai khong phai leak hay parity, ma la:

- thinking qua ngan
- khong co dau co duoi
- nhieu luc chi la 2-3 cau nhan xet xep canh nhau
- nghe nhu "renderer beats" hon la mot dong suy tu co chien luoc

Moc user phan anh:

> "Khoan, minh can nhan manh..."
>
> "Phai nhac them..."

Day la dung lane, nhung chua co `reasoning arc`.

## Huong sua

Sua trong:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_draft_service.py`

Nhung thay doi chinh:

1. Tu "xin vai beat hop le" thanh "xin 4 beat co vai tro ro":
   - observe
   - strategy / framing
   - doubt / self-correction
   - decision / response plan

2. Them `arc check`
   - neu draft < 4 beat hoac mo bai qua answer-ish
   - coi nhu chua dat

3. Them `repair pass`
   - khi draft chua dat, goi them 1 lan de viet lai
   - prompt repair noi ro:
     - beat dau phai bat vao cho de nham / trigger / pham vi
     - beat giua phai co chon goc + tu ra lai
     - beat cuoi phai khoa cach Wiii se go roi

4. Them anti-repetition manh hon
   - duplicate-ish detection bang token overlap
   - chan kaomoji / decorative aside trong body
   - chan mot so opener answer-ish trong beat dau

## Test

Focused suites:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_draft_service.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_supervisor_agent.py`

Ket qua:

- `99 passed`

## Live probe

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-arc-sync-2026-03-30-r3.json`

Prompt:

- `Giai thich Quy tac 15 COLREGs`

Ket qua live:

```text
Quy tắc 15, tình huống cắt mặt. Mình đang hình dung ra hai con tàu đang tiến lại gần nhau trên hướng gần đối đầu, một bên nhìn thấy bên kia ở phía mạn phải.

Thay vì liệt kê điều luật khô khan, mình sẽ dùng hình ảnh một ngã tư trên biển. Tàu nào thấy đối phương ở mạn phải thì tàu đó phải nhường đường, đơn giản như việc nhường xe ở vòng xuyến vậy.

Khoan, phải nhấn mạnh thêm là tàu nhường đường không được cắt ngang phía trước mũi tàu kia. Nếu giải thích mà thiếu ý này thì dễ gây nguy hiểm thực tế lắm.

Sẽ diễn đạt bằng ngôn ngữ đời thường nhất có thể, kết hợp với một ví dụ về việc chuyển hướng sớm để người nghe dễ hình dung sự chủ động cần thiết.
```

## Danh gia

Tien bo that:

- da co 4 nhac ro hon
- co "bat bai toan" + "chon goc" + "tu ra lai" + "chot cach tra loi"
- bot han cam giac 2 cau lap y

Nhung van chua la diem cuoi:

- beat dau van con hoi "gioi thieu de tai" hon la "bat cho de nham"
- mot so run van mo bang `Quy tac 15...` hoi sat answer lane
- tutor gray rail da co chien luoc hon, nhung van co the them "meta-cognitive turn" de song hon nua

## Bieu do tien trien

- Stage 1: leak cleanup -> done
- Stage 2: sync/stream authority -> done
- Stage 3: tutor LLM-authored draft -> done
- Stage 4: reasoning arc / repair pass -> done
- Stage 5 tiep theo: keo beat dau ra xa answer lane hon, tang strategic flow theo mau "nhan ra bai toan -> chon goc -> tu ra -> chot"
