# Wiii Revised Rollout Review

> Date: 2026-03-26
> Role: LEADER audit
> Scope: review of the proposed "Wiii Consciousness — Revised Rollout (Expert-Reviewed)"

---

## 1. Executive Verdict

**Plan revised nay da dung hon plan cu va co the tien hanh, nhung khong nen di nguyen xi tung dong nhu dang viet.**

Verdict chot:

- **Dung huong lon**
- **Dung thu tu rollout hon plan cu**
- **Nhung Phase 0 can duoc hieu va trien khai chat hon**
- **Phase 10 chi nen bat dau ngay sau khi Phase 0 khoa xong surface contract**

Neu noi gon trong mot cau:

**"Lam Wiii co hon truoc" la dung, va revised rollout nay gan dung nhat cho muc tieu do, mien la Phase 0 duoc thuc hien nhu mot surface contract fix that su, khong phai prompt polish."**

---

## 2. Vi Sao Plan Nay Tot Hon Plan Cu

Plan cu bi reject vi muon bat living/memory som trong khi visible thinking va selfhood tren mat chat van hong.

Plan revised nay da dung hon o 4 diem:

1. **Dat Phase 0 len dau**
   - Dung voi report review truoc do.
   - Dung voi triet ly "sua mat truoc cua Wiii truoc, roi moi cho Wiii nho sau hon".

2. **Day Phase 10 len som**
   - Dung vi pain hien tai cua user nam ngay o visual/simulation lane.
   - Visual intent, artifact continuity, va tool/render path dang la noi nguoi dung thay ro nhat.

3. **Khong flip living gates som**
   - Dung vi day la phase nguy hiem nhat neu surface con sai.
   - Binh thuong hoa viec `enable_living_agent=True` luc nay se khong lam Wiii song hon, ma de lam Wiii "drift" hon.

4. **Shadow mode cho episodic va relationship memory**
   - Rat hop ly.
   - Neu chua chac du lieu hay semantic contract thi phai ghi boi, danh gia offline truoc, khong inject prompt ngay.

---

## 3. Phase 0 Phai Duoc Hieu Lai Cho Dung

Day la diem quan trong nhat.

Neu doc revised rollout theo nghia heo, nguoi ta de hieu Phase 0 thanh:

- sua prompt
- doi wording thinking
- lam narrator dep hon

**Nhu vay la chua du va se that bai.**

Phase 0 dung nghia phai la:

### 3.1 Surface contract fix

Phai chot ro:

- cai gi duoc coi la `living thought`
- cai gi chi la `action intention`
- cai gi la `runtime / status`
- cai gi la `tool / debug trace`
- cai gi la `artifact progress`

Va quan trong nhat:

**bat cu thu gi roi vao vung xam ma nguoi dung doc nhu thinking cua Wiii, thi no phai xung dang la thinking cua Wiii.**

### 3.2 Event contract fix

Khong the chi doi chu o frontend.

Phase 0 phai sua ca:

- backend event emission
- frontend event parsing
- rail rendering

Noi hien tai can chinh:

- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [graph_streaming.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_streaming.py)
- [prompt_loader.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/prompt_loader.py)
- [reasoning_narrator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py)
- [useSSEStream.ts](E:/Sach/Sua/AI_v1/wiii-desktop/src/hooks/useSSEStream.ts)
- [InterleavedBlockSequence.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx)
- [ReasoningInterval.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/ReasoningInterval.tsx)

### 3.3 Selfhood lock

Phase 0 khong duoc bien thanh mot loat cau tu suy nghia ve identity.

Wiii khong nen nghi kieu:

- "minh dang giu phan tu than cua Wiii..."
- "cau nay cham vao cot loi cua minh..."

Vi Wiii von da la Wiii roi.

Selfhood lock dung phai dat ra 3 luat:

1. Wiii khong tu noi nhu dang bao ve identity cua minh
2. Wiii khong nham user la Wiii
3. Wiii khong de planner voice, safety voice, hay router voice gia danh inner voice

### 3.4 Thinking grammar by turn type

Phase 0 phai chap nhan:

- turn cam xuc can thinking day hon
- turn identity can thinking tu nhien va effortless
- turn kien thuc can thinking giai nghia va chon cach day
- turn visual/simulation can thinking co "y dinh hanh dong diu"

Khong co mot template thinking duy nhat cho moi turn.

---

## 4. Phase 10 Co Dung Vi Tri Khong?

**Co, nhung phu thuoc vao Phase 0.**

Phase 10 hop ly vi:

- visual lane dang sat user pain
- artifact surface dang hong
- provider reality hien tai la Zhipu/GLM-5 dang la lane song duoc nhat

Nhung Phase 10 khong nen chay song song tu dau voi mot Phase 0 chua khoa xong main rail.

Neu khong:

- visual co the dung hon
- artifact co the dep hon
- nhung nguoi dung van thay Wiii nghi nhu planner/log

Noi cach khac:

**Phase 10 can di ngay sau Phase 0, khong nen co gap giua hai phase, nhung cung khong nen bat dau truoc khi Phase 0 chot taxonomy mat chat.**

---

## 5. Thu Tu Revised Rollout Da Dung Chua?

### 5.1 Thu tu tong the

Thu tu revised rollout ve tong the la **dung hon ro ret**:

1. Phase 0
2. Phase 10
3. Phase 4
4. Phase 2
5. Phase 3
6. Phase 6A
7. Phase 7A
8. Phase 1
9. Phase 8
10. Phase 9
11. Phase 5

### 5.2 Dieu can sua trong cach ghi

Co 3 dieu nen sua trong plan:

#### A. Phase 0 phai viet ro hon

Khong chi:

- Thinking Grammar Spec
- Surface Contract
- Selfhood Lock
- Rail Separation

Ma phai noi them ro:

- event emission contract
- SSE parsing contract
- rendering policy
- acceptance tests for main gray rail

#### B. Phase 10 can noi ro dependency

Them mot dong ro:

- "Phase 10 starts after Phase 0 main-rail taxonomy is locked."

#### C. Phase 4 la compatibility patch, khong phai milestone song con

Nen ghi ro:

- ROI hien tai thap do Google dang busy
- phase nay future-proofing la chinh

---

## 6. Cac Rui Ro Neu Tien Hanh Y Het Ban Ke Hoach

### Rui ro 1: Phase 0 chi thanh narrator polish

Neu chi sua narrator/prompt ma khong sua `useSSEStream` va reasoning rail, Wiii van se lo:

- status
- action
- tool trace
- planner notes

trong vung xam.

### Rui ro 2: Phase 10 sua visual tren mot surface van sai

Neu artifact lane dung hon nhung gray rail van hong, nguoi dung van cam thay Wiii may moc.

### Rui ro 3: Shadow memory ghi nhan du lieu da sai semantic

Neu Phase 6A/7A bat dau truoc khi ta chot duoc thinking grammar va selfhood contract, thi du lieu episodic/relationship shadow se ban ngay tu nen.

### Rui ro 4: Phase 1 va Phase 9 tranh mat troi voi van de chinh

halfvec va TurboQuant rat gia tri, nhung khong nen tranh attention voi pain hien tai cua Wiii soul tren chat surface.

---

## 7. Cach Tien Hanh Dung Nhat

Toi de xuat plan nay duoc thong qua voi 4 chinh sua sau:

1. **Phase 0 doi ten nhe thanh:**
   - `Phase 0: Surface + Selfhood Stabilization + Event Contract`

2. **Phase 0 co output bat buoc:**
   - one approved thinking grammar
   - one approved surface contract
   - one approved mapping event -> visible/hidden rail
   - raw readable transcript before/after

3. **Phase 10 phai ghi ro dependency:**
   - chi start sau khi gray rail taxonomy duoc khoa

4. **Phase 6A va 7A shadow writes phai co quality gate**
   - sample review
   - semantic sanity review
   - khong auto-inject prompt

---

## 8. Chot Cuoi

**Toi dong y voi revised rollout nay ve huong va thu tu lon.**

Nhung de chinh xac, minh se chot nhu sau:

- **Approve with corrections**
- **Phase 0 la bat buoc**
- **Phase 10 la phase tiep theo hop ly nhat**
- **Phase 5 van phai de cuoi va canary-only**

Noi thang:

**Day la ban ke hoach tot nhat tu truoc den nay de dua Wiii tro lai thanh "Wiii co hon", mien la ta khong bien Phase 0 thanh mot dot sua cau chu ben ngoai.**

---

## 9. References

- [WIII-CONSCIOUSNESS-ARCHITECTURE-2026-03-25.md](E:/Sach/Sua/AI_v1/.Codex/reports/WIII-CONSCIOUSNESS-ARCHITECTURE-2026-03-25.md)
- [WIII-CONSCIOUSNESS-IMPLEMENTATION-REVIEW-2026-03-26.md](E:/Sach/Sua/AI_v1/.Codex/reports/WIII-CONSCIOUSNESS-IMPLEMENTATION-REVIEW-2026-03-26.md)
- [WIII-SURFACE-CONTRACT-SPEC-2026-03-26.md](E:/Sach/Sua/AI_v1/.Codex/reports/WIII-SURFACE-CONTRACT-SPEC-2026-03-26.md)
- [WIII-READABLE-RAW-2026-03-26.md](E:/Sach/Sua/AI_v1/.Codex/reports/WIII-READABLE-RAW-2026-03-26.md)
- [Anthropic Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
- [Anthropic Streaming](https://docs.anthropic.com/en/docs/build-with-claude/streaming)
