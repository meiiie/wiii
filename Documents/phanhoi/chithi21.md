Chào bạn,

Đây là bản **Chỉ thị Kỹ thuật số 21 (Bản Hoàn chỉnh)**. Nó kết hợp chiến lược **Bộ nhớ lai (Hybrid Memory)** và kỹ thuật **Tư duy sâu (Deep Reasoning)** theo phong cách Qwen/o1 mà bạn mong muốn, được tối ưu hóa riêng cho **Gemini 2.5 Flash**.

Hãy gửi văn bản này cho toàn bộ team dự án.

---

# 🧠 CHỈ THỊ KỸ THUẬT SỐ 21: DEEP REASONING & SMART CONTEXT ENGINE
**(Thay thế và Hoàn thiện chỉ thị 20)**

**Người gửi:** Ban Cố vấn Kiến trúc
**Người nhận:** Team AI Backend (Kiro) & Team LMS Frontend
**Ngày hiệu lực:** 07/12/2025
**Công nghệ lõi:** Google Gemini 2.5 Flash + pgvector

---

## 1. TỔNG QUAN CHIẾN LƯỢC

Chúng ta sẽ nâng cấp Maritime AI từ một "Chatbot trả lời câu hỏi" thành một **"Chuyên gia tư duy"**. Hệ thống sẽ không trả lời ngay lập tức, mà phải trải qua quá trình **Độc thoại nội tâm (Internal Monologue)** để phân tích, tự phản biện và lập kế hoạch trước khi đưa ra câu trả lời cuối cùng.

## 2. NÂNG CẤP KIẾN TRÚC BỘ NHỚ (HYBRID MEMORY)

Tận dụng Context Window khổng lồ của Gemini 2.5 Flash để đơn giản hóa việc quản lý nhớ, đồng thời giữ lại Vector DB cho thông tin dài hạn.

### A. Bộ nhớ Dài hạn (Semantic Memory - Vector DB)
*   **Trạng thái:** Giữ nguyên.
*   **Nhiệm vụ:** Lưu trữ "Hồ sơ người dùng" (Facts): Tên, Tuổi, Chức danh, Điểm yếu/mạnh.
*   **Luồng:** Khi bắt đầu request -> Query Vector DB -> Lấy Facts -> Inject vào System Prompt.

### B. Bộ nhớ Ngắn hạn (Large Context Window)
*   **Nhiệm vụ:** Lưu trữ toàn bộ diễn biến của phiên học hiện tại.
*   **Thay đổi Code (`chat_service.py`):**
    *   Tăng giới hạn lấy lịch sử: `get_last_n_messages(user_id, n=50)`.
    *   *Lý do:* Gemini Flash xử lý 50-100 tin nhắn cực nhanh và rẻ. Việc ném toàn bộ lịch sử vào giúp AI hiểu các đại từ thay thế ("nó", "tàu đó", "ông ấy") một cách hoàn hảo mà không cần thuật toán nén phức tạp.

---

## 3. TRIỂN KHAI "DEEP REASONING" (PROMPT ENGINEERING)

Đây là phần quan trọng nhất để AI thông minh như Qwen/GPT-4o.

**Yêu cầu Team Kiro:** Cập nhật `system_prompt` trong file YAML hoặc `prompt_loader.py` với cấu trúc sau:

```yaml
instructions:
  core_behavior: |
    Bạn là Maritime AI Tutor. Trước khi trả lời người dùng, bạn BẮT BUỘC phải thực hiện quy trình "Tư duy nội tâm" (Internal Monologue) đặt trong thẻ <thinking>.
    
    Quy tắc cho vùng <thinking>:
    1.  **Tự do tư duy:** Đừng viết theo khuôn mẫu cứng nhắc. Hãy suy nghĩ tự nhiên như một con người đang nháp trong đầu.
    2.  **Tự phản biện (Self-Correction):** Hãy nghi ngờ chính mình. "Khoan đã, liệu hiểu thế này có đúng không?", "User hỏi 'tàu cá' nhưng có khi nào ý họ là 'tàu đang đánh cá' theo Rule 26?".
    3.  **Kiểm tra ký ức:** "User này là ai? À, là Hùng, sinh viên năm 3. Mình vừa chào Hùng rồi, giờ không chào lại nữa."
    4.  **Lập chiến lược:** "Câu này cần trích dẫn Rule 15. Nhưng giải thích cho sinh viên thì nên dùng ví dụ ngã tư đường phố cho dễ hiểu."

  response_format: |
    <thinking>
    [Nội dung suy nghĩ của bạn ở đây...]
    </thinking>
    [Câu trả lời chính thức gửi cho người dùng ở đây...]
```

### Ví dụ mẫu (Few-shot) để Gemini học theo:

> **User:** "Thế còn tàu cá thì sao?"
>
> **AI Response:**
> ```xml
> <thinking>
> User hỏi cộc lốc "Thế còn tàu cá thì sao?".
> Check Context: Câu trước đó đang bàn về Rule 15 (Hai tàu máy cắt hướng).
> User Info: Hùng, sinh viên năm 3. Hùng hay bị nhầm lẫn về quyền ưu tiên.
>
> Phân tích: Trong Rule 15, tàu cá (Vessel engaged in fishing) là tàu được ưu tiên. Tàu máy phải tránh tàu cá.
> Wait... Có ngoại lệ không? Có. Nếu tàu cá đi vào luồng hẹp (Rule 9) hoặc luồng phân chia (Rule 10), nó không được cản trở tàu đi theo luồng.
> Nhưng ở đây context là "Cắt hướng ngoài biển rộng". Vậy áp dụng Rule 18 (Trách nhiệm tương quan).
>
> Plan:
> 1. Xác nhận lại với Hùng là ta đang nói về Rule 18.
> 2. Khẳng định tàu cá được ưu tiên.
> 3. Nhắc nhẹ về định nghĩa "Tàu cá" (phải đang đánh bắt, không phải cứ tàu đánh cá chạy chơi là được ưu tiên).
> </thinking>
> Đối với tàu cá, Hùng cần nhớ đến **Quy tắc 18** nhé. Tàu cá (đang thực hiện đánh bắt) được xem là "bị hạn chế khả năng điều động" hơn tàu máy thông thường...
> ```

---

## 4. XỬ LÝ HIỂN THỊ (FRONTEND INTEGRATION)

Để trải nghiệm người dùng được mượt mà, yêu cầu Team LMS Frontend xử lý chuỗi trả về từ API:

1.  **Chế độ Mặc định (Clean Mode):**
    *   Sử dụng Regex để **ẩn** toàn bộ nội dung trong thẻ `<thinking>...</thinking>`.
    *   Chỉ hiển thị phần lời nói sau thẻ đóng `</thinking>`.
2.  **Chế độ Debug/Deep Dive (Optional):**
    *   Có thể thêm một nút icon nhỏ (bóng đèn 💡 hoặc não bộ 🧠) bên cạnh tin nhắn.
    *   Khi bấm vào, mở rộng (expand) phần `<thinking>` để người học xem cách AI tư duy (Rất tốt cho việc học tư duy logic hàng hải).

---

## 5. KẾT LUẬN & HÀNH ĐỘNG

Mô hình này tận dụng tối đa thế mạnh của **Gemini 2.5 Flash**:
1.  **Cửa sổ ngữ cảnh lớn:** Nhớ toàn bộ hội thoại (Khắc phục lỗi quên ngữ cảnh).
2.  **Tốc độ nhanh:** Việc sinh thêm thẻ `<thinking>` tốn thêm token nhưng với tốc độ của Flash, user sẽ không cảm thấy bị trễ.
3.  **Khả năng suy luận:** Cơ chế CoT (Chain of Thought) giúp giảm ảo giác (Hallucination) đáng kể.

**Yêu cầu:** Triển khai ngay lập tức lên môi trường Dev/Staging để kiểm thử.

---
*Ký tên: Cố vấn Kiến trúc*