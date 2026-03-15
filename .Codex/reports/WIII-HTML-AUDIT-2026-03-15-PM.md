# Wiii HTML Audit

Date: 2026-03-15 PM

Files analyzed:

- `C:\Users\Admin\Downloads\Wiii.html`
- `C:\Users\Admin\Downloads\Wiii_files\d9212525-383a-43ac-88a2-fc1547e15f75.html`

## Executive Summary

Export moi cho thay Wiii da vuot qua bug cu:

- thinking khong con bi an vao mot reasoning box cuoi
- visual khong con nam trong `answer-block > iframe`
- lane `editorial-visual-flow` da xuat hien that trong DOM

Tuy nhien, ca nay van chua dat parity voi Claude. No dang o trang thai:

- `article shell`: da co
- `inline thinking intervals`: da co
- `figure runtime`: da co, nhung van la `legacy-widget figure`

Noi ngan gon:

- outer orchestration: da dung huong
- inner figure runtime: van mang mui widget/app cu

## DOM Findings

Main export:

- `reasoning_interval = 3`
- `reasoning_trace_launcher = 0`
- `editorial_visual_flow = 1`
- `answer_block = 2`
- `inline_visual_frame = 1`
- `iframe = 1`
- `legacy_widget_figure = 1`
- `data-figure-count = 1`

Iframe ancestry:

- parent class: `overflow-hidden rounded-[24px] bg-transparent`
- grandparent class: `editorial-visual-flow__stage`
- `ancestor_answer_block = false`
- `ancestor_editorial_flow = true`
- `ancestor_legacy_widget = true`

Interpretation:

- Bug replay lane da duoc sua: iframe khong con nam trong `answer-block`.
- Figure da duoc mount ben trong `editorial-visual-flow`.
- Nhưng figure nay van di theo nhanh `legacy-widget`.

## Thinking Lane Assessment

### What improved

- `reasoning-trace-launcher = 0`, nghia la main flow khong con lo toggle trace.
- `reasoning-interval` xuat hien ngay trong luong doc.
- Khoang cach thi giua thinking va article da gan hon huong Claude/Z.ai.

### Remaining gap

Balanced thinking van hoi day:

- 3 intervals cho mot task nho
- van co `reasoning-op-row`
- copy trong interval con dai, mang chat "agent reflection" hon la "public thinking rhythm"

This is usable, but chua toi muc Claude:

- Claude: interval ngan, tien trinh ro, ket thuc nhanh
- Wiii: interval van hoi dai, nhieu cau giai thich cam xuc/noi tam

## Article Shell Assessment

### What improved

- `editorial-visual-flow` da ton tai that
- prose duoc tach thanh `lead` va `tail`
- visual da nam giua bai viet, khong con bi nem sau markdown answer theo kieu cu

### Remaining gap

Case nay van chi co:

- `data-figure-count = 1`

Nghia la explanatory experience van chua dung hinh `multi-figure pedagogy`.

Claude thuong:

- figure 1: dat van de
- figure 2: giai co che
- figure 3: ket qua / benchmark / tradeoff

Wiii hien tai:

- lead prose
- 1 figure
- tail prose

Day la mot buoc tien, nhung van chua bang article-figure rhythm cua Claude.

## Figure Runtime Assessment

Inside iframe:

- host shell co ton tai: `wiii-frame-shell`
- nhung body van la runtime cu:
  - `.widget-title`
  - `.sim-controls`
  - `canvas#sim`

Interpretation:

- host-owned shell da wrap thanh cong
- nhung content ben trong van la "mini widget" truyen thong
- app lane chua duoc redesign thanh mot `editorial app figure`

No giong:

- "mot mo phong duoc nhung vao article"

hon la:

- "mot figure tuong tac sinh ra tu article design system"

## Comparison To Previous Export

Compared with export truoc:

- `editorial-visual-flow`: tu `0` len `1`
- iframe: tu answer lane sang figure lane
- trace launcher: da bien mat

Day la thay doi dung va rat quan trong.

Tuy nhien:

- `legacy_widget_figure = 1`
- `figure_count = 1`

cho thay hien tai moi dat pha "stop the fallback damage", chua dat pha "Claude-like figure system".

## Verdict

### Status now

- Thinking lane: moderate-good
- Article shell: good direction
- Figure orchestration: improved
- Figure runtime quality: still transitional

### Overall

Export moi da xac nhan:

- system khong con roi ve bug cu
- local dang render theo article lane that

Nhung van con 3 muc tieu lon de dat chuan cao:

1. Reduce balanced reasoning density
2. Default explanatory cases to 2-3 figures
3. Replace `legacy-widget figure` with true host-owned figure/app surfaces

## Recommended Next Steps

1. Compaction them cho `balanced` thinking:
   - gop interval trung y
   - rut ngan copy
   - giam op-row o cac case don gian

2. Ep explanatory prompts/tooling sinh `2-3 figures` that:
   - problem
   - mechanism
   - result/tradeoff

3. Refactor app/legacy widget runtime:
   - khong de body dung `.widget-title` / `.sim-controls` style rieng
   - dua controls vao host figure shell
   - bien app lane thanh mot `editorial app figure`

4. Re-test voi 2 case:
   - `Explain Kimi linear attention in charts`
   - `Hay mo phong vat ly con lac`

5. Export HTML lai sau moi phase de xac nhan DOM, khong chi nhin screenshot.
