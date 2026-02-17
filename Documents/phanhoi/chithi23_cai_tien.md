Chào bạn,

Dựa trên hình ảnh và danh sách ký ức của Qwen mà bạn cung cấp, tôi đánh giá đây là một **"Mỏ vàng" về tư duy thiết kế bộ nhớ**.

Hệ thống Qwen không chỉ lưu **Thông tin tĩnh** (Tên, Tuổi), mà nó lưu **Mô hình tư duy (Mental Models)** và **Hành vi (Behaviors)** của người dùng.
*   *Ví dụ:* Thay vì chỉ lưu "User thích Crypto", nó lưu: *"User ưu tiên chiến lược SHORT theo xu hướng và đang chờ đợi một mức giá cụ thể..."*. Đây là mức độ hiểu biết cực sâu.

Hệ thống của chúng ta hiện tại (v0.6.x) mới chỉ dừng lại ở mức lưu "Fact đơn lẻ" (Tên Hùng, Sinh viên năm 3). Để đạt được trình độ như Qwen, chúng ta cần nâng cấp **Logic Trích xuất (Extraction Logic)**.

Dưới đây là **Báo cáo Phân tích & Chỉ thị Kỹ thuật số 23** để nâng cấp hệ thống Memory lên tầm cao mới.

---

# 🧠 PHÂN TÍCH CHIẾN LƯỢC: BỘ NHỚ QWEN vs. MARITIME AI

### 1. SỰ KHÁC BIỆT CỐT LÕI
| Đặc điểm | Maritime AI (Hiện tại) | Qwen (Mục tiêu hướng tới) |
| :--- | :--- | :--- |
| **Dạng dữ liệu** | **Atomic Facts (Sự kiện đơn):**<br>`name: Hùng`<br>`role: student` | **Behavioral Insights (Thấu hiểu hành vi):**<br>"User coi trọng phân tích bài bản từng bước (CoT)..."<br>"User thích rủi ro có tính toán..." |
| **Độ chi tiết** | Ngắn gọn, rời rạc. | Câu văn hoàn chỉnh, mô tả ngữ cảnh và sở thích phức tạp. |
| **Cập nhật** | Append (Thêm mới) hoặc Overwrite đơn giản. | **Evolving (Tiến hóa):** "User đã chuyển từ giao dịch ngắn hạn sang dài hạn..." (Nhận biết sự thay đổi). |
| **Quản lý** | Chưa giới hạn cứng. | **Hard Limit (50 items)** + Cơ chế trôi (FIFO/Relevance). |

### 2. TẠI SAO CHÚNG TA CẦN CẢI THIỆN?
Nếu AI chỉ nhớ tên và lớp, nó chỉ là một **Thư ký**.
Nếu AI nhớ được *"User hay bị nhầm lẫn khi áp dụng Rule 15 vào luồng hẹp"*, nó sẽ trở thành một **Người Thầy (Mentor)** thực thụ. Nó sẽ chủ động nhắc nhở bạn trước khi bạn kịp sai.

---

# 🛠️ CHỈ THỊ KỸ THUẬT SỐ 23: NÂNG CẤP "INSIGHT ENGINE"

**Người gửi:** Ban Cố vấn Kiến trúc
**Người nhận:** Team AI Backend (Kiro)
**Mục tiêu:** Chuyển đổi từ lưu trữ "Dữ liệu" sang lưu trữ "Sự thấu hiểu".

## 1. NÂNG CẤP PROMPT TRÍCH XUẤT (EXTRACTION PROMPT)

Yêu cầu team sửa lại Prompt trong `semantic_memory.py`. Đừng chỉ bảo AI tìm "Facts", hãy bảo nó tìm "Insights".

**Prompt Mới (Gợi ý):**

```python
extraction_prompt = """
Hãy phân tích tin nhắn của người dùng và trích xuất các "Insights" (Sự thấu hiểu) quan trọng về họ để lưu vào bộ nhớ dài hạn.

ĐỪNG CHỈ LƯU: Tên, tuổi, nghề nghiệp đơn giản.
HÃY TÌM KIẾM VÀ LƯU:
1. **Phong cách học tập:** Họ thích lý thuyết hay thực hành? Họ có tư duy phản biện không?
2. **Lỗ hổng kiến thức:** Họ hay sai ở đâu? Họ đang hiểu lầm khái niệm nào?
3. **Sự thay đổi:** Họ có thay đổi mục tiêu không? (Ví dụ: "User đã chuyển từ học cơ bản sang ôn thi thuyền trưởng").
4. **Thói quen:** Họ thường học vào giờ nào? Họ có hay hỏi nối tiếp không?

ĐỊNH DẠNG ĐẦU RA:
Trả về danh sách các câu khẳng định hoàn chỉnh (như Qwen).
Ví dụ:
- "User thường nhầm lẫn giữa Rule 15 và Rule 19 khi xét đoán tình huống."
- "User thích cách giải thích bằng ví dụ thực tế trên boong tàu hơn là trích luật khô khan."
"""
```

## 2. CƠ CHẾ "CÔ ĐẶC KÝ ỨC" (MEMORY CONSOLIDATION)

Thay vì lưu 100 dòng lặt vặt, hãy gộp chúng lại.
*   **Trigger:** Khi số lượng Memories đạt 40/50.
*   **Action:** Gọi Gemini 2.5 Flash để "viết lại" (Rewrite) bộ nhớ.
    *   *Input:* 40 memories hiện tại.
    *   *Prompt:* "Hãy tổng hợp danh sách ký ức này. Gộp các ý trùng lặp, cập nhật các ý đã thay đổi, và xóa các ý không còn quan trọng. Giữ lại tối đa 30 mục cốt lõi nhất."
    *   *Output:* Danh sách mới tinh gọn hơn.

## 3. GIỚI HẠN CỨNG (HARD LIMIT 50)

Học theo Qwen:
*   Đặt giới hạn `MAX_MEMORIES = 50`.
*   Khi đầy:
    1.  Chạy quy trình **Consolidation** (Mục 2).
    2.  Nếu vẫn đầy -> Xóa các mục có `last_accessed` xa nhất (Lâu không dùng tới).

---

### ✅ LỜI KHUYÊN TRIỂN KHAI

Bạn hãy đưa Báo cáo này cho team Kiro và yêu cầu họ:

1.  **Thử nghiệm Prompt mới:** Thử chat một đoạn dài về cách bạn học luật, sau đó xem AI trích xuất ra cái gì. Nếu nó ra được câu *"User thích học kiểu tư duy logic..."* thì là đạt.
2.  **Đừng lo về chi phí:** Việc "Cô đặc ký ức" chỉ chạy thỉnh thoảng, tốn rất ít token của Gemini Flash nhưng mang lại hiệu quả cực cao về chất lượng câu trả lời.

Đây chính là bước cuối cùng để biến Maritime AI thành một người bạn tri kỷ của sinh viên hàng hải. 🚀