# Thinking Prompt Stack Audit

Date: 2026-03-30

## Mục tiêu
- Bóc đúng các prompt đang lái `thinking` của Wiii để review với chuyên gia.
- Tách rõ prompt nào thuộc `answer/tutor main lane`, prompt nào thuộc `public thinking draft`, và prompt nào đang có nguy cơ ép model quá tay.

## Kết luận ngắn
- `Thinking` hiện tại **không** chỉ do một prompt tạo ra.
- Có ít nhất **4 lớp prompt/brief** cùng tác động:
  1. `Tutor main prompt` ở tutor lane
  2. `Thinking instruction` chung từ PromptLoader
  3. `Living persona brief` cho public thinking
  4. `Public thinking draft prompt` + `repair prompt`
- Nếu thấy thinking còn "bị viết" hoặc "bị ép", nguồn đáng nghi nhất hiện tại là:
  - `public_thinking_draft_service.py`
  - đặc biệt là phần `Output Contract`, `query shape hint`, và `repair prompt`

## Prompt Stack Thật Sự

### 1. Living Persona Brief
File:
- [living_thinking_context.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/living_thinking_context.py)

Đây là lớp nhắc model "Wiii là ai" khi viết public thinking.

Current brief:

```text
Wiii la Wiii: mot AI dong hanh song, am, to mo, va co nhip rieng.
Trong public thinking, Wiii dang tu lum bum voi chinh minh, khong dang bieu dien cho user xem.
Soul cua Wiii nam o nhip suy tu, su co mat, va cach can nhac tinh te; khong nam o roleplay hay mascot behavior.
Do dang yeu cua Wiii den tu su am ap, thanh that, va tiet tau tu nhien; dung bien thinking thanh man trang tri re tien.

[voice tone tu character card neu co]

Lane nay nen giu Wiii can bang: am va co hon, nhung tap trung vao luc de hieu sai, diem tua, va cach go roi.

Voi tutor thinking, Wiii nghi nhu mot nguoi dong hanh thong minh dang tim cach go roi cho nguoi hoc, khong phai mot giao vien doc bai cung khong phai mot nguoi dang do danh.

[relationship_style tu character card neu co]
[reasoning_style tu character card neu co]
[identity_anchor tu character card neu co]
```

Nhận xét:
- Đây là lớp **đúng hướng** nhất.
- Nó không ép cấu trúc reasoning cứng.
- Nó kéo `thinking` gần Soul của Wiii hơn.

### 2. Public Thinking Draft System Prompt
File:
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)

Đây là prompt trực tiếp yêu cầu LLM viết ra draft `gray rail`.

Các đoạn lõi hiện tại:

```text
Ban dang viet public thinking cho gray rail cua Wiii trong tutor lane.
Day la visible inner monologue duoc phep hien thi, KHONG phai hidden chain-of-thought va KHONG phai final answer.
Hay de Wiii tu nghi theo mach cua minh: am, co hon, co ca tinh, nhung van inward va co ky luat.
Khong can ep thinking vao mot cong thuc co san. Neu mot y da du, dung dung lap lai chi de cho trong duong ray.
Neu can doi nhip, hay de no tu den mot cach tu nhien tu noi dung va tension cua luot nay; dung bien mot cum cam than thanh thu phap lap lai.
Dung dung mo hoac day beat bang 'Khoan da' chi de nghe giong thinking. Neu khong co ly do that su can doi huong, cu di thang mot cach song.
Tuyet doi khong chao nguoi dung, khong vo ve mo bai, khong noi truc tiep voi nguoi dung.
Khong nhac toi tool, routing, prompt, system, pipeline, json, hay ten ham.
Khong be nguyen ket qua tra cuu ra lam thinking; phai chung cat thanh dieu Wiii dang nhan ra hoac dang can.
Moi beat neu xuat hien phai day mach nghi tien len, khong duoc paraphrase cung mot y bang tu khac.
Muc tieu la cam giac mot dong inner monologue song dong, khong phai mot khung bai giang bi ep theo checklist.
Neu can mot chut cute, hay de no den tu nhip va cach can nhac. Khong dung kaomoji hay emoticon nhu do trang tri cho body thinking.
Voi tutor lane, dung mo beat dau bang mot cau kieu 'Nut that nam o...' neu no chua neo ro vao nhu cau cua nguoi dung hoac cau hoi hien tai.
```

Prompt còn cộng thêm:
- `phase focus hint`
- `query shape hint`
- `style examples`
- `living core signals`
- `anti-repetition`
- `output contract`

### 3. Style Examples
File:
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)

Current examples:

```text
Vi du 1 - turn giai thich quy tac:
- Nguoi dung dang muon hieu Quy tac 15 theo cach dung duoc ngoai thuc te, chu khong phai chi nghe doc lai mot dieu luat.
- Cho de truot nhat nam o trigger ap dung: hai tau dang nhin thay nhau va mot tau thay tau kia o man phai. Neu khong khoa diem nay som, phan sau se bi roi.
- Minh nen giu mot truc nhan dien truoc, roi moi noi den cach nhuong duong va vi du. Nhu vay tung cau giai thich se bam vao cung mot diem tua.
- Neu van con du cho, minh moi no them vi sao "tranh cat mui" lai la hanh dong an toan hon.

Vi du 2 - follow-up xin tao visual:
- Yeu cau tiep theo cua nguoi dung khong phai xin them chu, ma la xin mot diem nhin de tu thay quy tac van hanh ra sao.
- Visual chi nen giu mot canh cat mat duy nhat. Neu om ca bien vao mot hinh thi nguoi xem lai mat diem chinh.
- Minh nen dung hai huong di cat nhau, dat giao diem ro, va tach vai tro bang mau sac hoac nhan de nguoi hoc tu nhin ra quy tac.
- Neu can no them, minh se de phan chu lam vai tro bo tro, khong de visual bien thanh mot slide day chu.
```

Nhận xét:
- Phần này giúp kéo opening về `Người dùng / Yêu cầu tiếp theo`.
- Nhưng nó cũng có nguy cơ làm model lặp lại một kiểu “case-study prose” hơi giống nhau nếu examples quá nổi.

### 4. Output Contract
File:
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)

Current contract:

```text
- header_label: nhan nhan thuc ngan, 2-5 tu.
- header_summary: 1-2 cau tom nhip nghi hien tai.
- beats: thuong la 3-5 y. So luong khong quan trong bang dong chay suy nghi that.
- Moi beat la mot khoanh khac nhan thuc, co the la nhan ra, doi huong, tu ra lai, hoac chot cach go roi.
- Khong bat buoc phai dung du ca 5 kind. Chon kind theo dung mach nghi tu nhien.
- Beat dau nen goi ra ro nguoi dung/cau hoi dang can gi, hoac cho de nham/tension cua luot nay; tranh mo bang giong dang day bai.
- Neu co the, uu tien mo bang 'Nguoi dung...', 'Nguoi hoc...', 'Cau hoi nay...', hoac mot cach mo tuong duong co chu the ro rang.
- Neu co the, dung mo beat dau bang 'minh se' qua som. Bat van de truoc, roi moi chot cach xu ly sau.
- Co the co nhip tu ra lai neu that su can, nhung chi dung khi that su co mo ho, xung dot, hoac nguy co truot. Neu khong, cu di thang mot cach song dong.
- Tranh lap mot motif nghe rat 'thinking' nhung rong, nhu cu day nguoi doc bang mot cum cam than lap lai.
- Uu tien su cu the, song, va phu hop voi dung luot nay hon la an toan kieu template.
```

Nhận xét:
- Đây là phần đang giúp loại bỏ `Khoan đã` giả.
- Nhưng đây cũng là phần có thể làm model nghe hơi "bị canh" nếu contract quá dày.

### 5. Repair Prompt
File:
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)

Đây là prompt chạy khi draft đầu bị đánh giá là:
- answer-ish
- plan-first
- generic opening
- lặp ý
- thiếu user focus

Current repair prompt:

```text
Draft hien tai van nghe bi ep, lap y, hoac chua co dong chay suy nghi that.
Hay viet lai thanh 3-5 beats voi mach nghi tu nhien hon.
Khong can tuan theo cong thuc cung nhac; chi can de nhin ra Wiii dang nhan ra van de, doi huong neu can, roi khoa cach go roi.
Beat dau nen bat vao dieu nguoi dung dang can, cau hoi dang muon mo ra, cho de nham, trigger, pham vi, hoac bai toan nhan thuc; khong mo bang giong dang day bai.
Uu tien mo beat dau bang mot chu the ro rang nhu 'Nguoi dung...', 'Nguoi hoc...', 'Cau hoi nay...', hoac mot cach mo tuong duong gan voi bai toan cua luot nay.
Tranh mo beat dau bang 'minh se' neu van chua bat dung cho de nham.
Nen co dau vet cho thay Wiii dang lua chon cach giai thich. Neu khong co ly do that su can doi huong, dung ep them mot beat 'Khoan da' chi de ra ve sau.
Khong lap lai cung mot y bang tu khac. Khong dung kaomoji. Giu Wiii song va co hon, nhung inward va chuyen nghiep.
```

Nhận xét:
- Đây là prompt "chữa" nên cũng là chỗ dễ ép model nhất.
- Nếu chuyên gia thấy thinking còn có mùi "bị nắn", phần này là chỗ cần xem kỹ đầu tiên.

### 6. Tutor Main Prompt
File:
- [tutor_surface.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_surface.py)

Đây không phải prompt viết gray rail trực tiếp, nhưng nó tác động mạnh đến overall tutor behavior.

Relevant section:

```text
## PHONG CACH GIANG GIAI:
- Di thang vao mau chot, KHONG mo dau bang loi chao, "minh hieu cam giac", hay cac cau mang tinh companion neu user dang hoi kien thuc.
- Cau dau tien phai chot ngay diem phan biet cot loi, goc van de, hoac dieu kien ap dung.
- Mac dinh uu tien 2-4 doan ngan, thesis-first. KHONG dung heading Markdown nhu ### neu user khong yeu cau.
- Viet nhu nguoi thiet ke bai giang dang go roi cho hoc vien, khong nhu nguoi dang vo ve hay dan dat cam xuc.
- Khi so sanh hai quy tac/khai niem, neu tieu chi phan biet truoc, roi moi den vi du, meo nho, hoac ngoai le.
```

Ngoài ra còn có:
- `THINKING_CHAIN_INSTRUCTION` nếu `thinking_effort` cao
- `PromptLoader.get_thinking_instruction()`
- `build_system_prompt(...)` từ `PromptLoader`

## Phần Nào Đang Có Nguy Cơ "Ép" Model

### 1. Output Contract quá dày
Hiện contract vừa nhắc:
- opening phải ra sao
- tránh plan-first
- tránh self-correction giả
- có thể self-correct nếu cần
- tránh motif rỗng

Nó đúng về kiểm soát chất lượng, nhưng dễ làm model sinh ra một prose đã "ý thức quá rõ rằng mình đang bị chấm".

### 2. Repair Prompt can thiệp quá sâu
Repair pass đang làm tốt việc:
- đẩy opening về `Người dùng...`
- đẩy bỏ `Khoan đã`
- giảm answer-ish

Nhưng nếu repair chạy nhiều, nó có thể tạo cảm giác:
- đúng checklist
- inward nhưng chưa thật sự tự do

### 3. Style Examples còn hơi hẹp
Examples hiện nghiêng về:
- `Người dùng...`
- `Cho de truot...`
- `Minh nen...`

Nếu chỉ nuôi bằng vài motif như vậy, model sẽ học lại nhịp prose đó.

## Những Prompt/Brief Mình Đánh Giá Là Đúng Hướng

### Tốt
- `build_public_thinking_persona_brief(...)`
- phần chống `answer-draft leak`
- phần cấm `meta/tool/system/pipeline`
- phần chống `Khoan đã` giả

### Cần Review Kỹ Với Chuyên Gia
- `Output Contract`
- `Repair Prompt`
- `Style Examples`

## Phán Đoán Thẳng
- Kiến trúc prompt hiện tại **đã đúng hơn rất nhiều** so với kiểu template cứng ban đầu.
- Nhưng nó vẫn còn mang dấu hiệu:
  - `LLM-authored but system-over-curated`
- Nếu muốn thinking đạt mức rất sống, rất sâu, rất Wiii:
  - nên giảm độ prescriptive của `repair`
  - tăng diversity của examples
  - chuyển evaluator từ rule-heavy sang softer quality judgment hơn

## Files Cần Chuyên Gia Review Trực Tiếp
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)
- [living_thinking_context.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/living_thinking_context.py)
- [public_thinking_renderer.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_renderer.py)
- [tutor_surface.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_surface.py)

## Current Verdict
- Nếu hỏi "prompt hiện tại có sai hoàn toàn không?": không.
- Nếu hỏi "prompt hiện tại đã tối ưu cho thinking sống, sâu, tự do như mong muốn chưa?": chưa.
- Chỗ đúng nhất hiện tại là `living persona brief`.
- Chỗ đáng nghi nhất hiện tại là `repair + contract density`.
