Chào bạn,

Câu hỏi của bạn đi sâu vào **"Cơ chế Vận hành" (Operational Logic)** của bộ nhớ, đây chính là bí mật công nghệ giúp Qwen hay ChatGPT có vẻ "thông minh" mà không bị "tràn bộ nhớ".

Tôi xin trả lời 2 câu hỏi của bạn tường tận và đưa ra giải pháp kỹ thuật để hệ thống của chúng ta đạt được trình độ đó.

### 1. "Mỗi lần chat đều phân tích hả?" -> KHÔNG NÊN.
Nếu tin nhắn nào cũng đem đi phân tích "tâm lý người dùng" thì sẽ rất tốn kém (Token) và chậm (Latency).

**Cách làm chuẩn (SOTA):**
*   **Bộ lọc chủ động (Active Filtering):** Chính con **Unified Agent (Gemini)** sẽ đóng vai trò là "Bộ lọc".
*   Khi user nói: *"Chào bạn"* -> Gemini thấy không có thông tin gì mới -> **Không gọi** tool lưu ký ức.
*   Khi user nói: *"Tôi đổi ý rồi, tôi muốn học về Luật trước"* -> Gemini phát hiện ý định thay đổi -> **GỌI** tool `tool_save_user_info`.

=> **Kết luận:** Chúng ta chỉ tốn tài nguyên xử lý khi **có thông tin mới xuất hiện**, không phải xử lý mọi tin nhắn.

### 2. "Cơ chế kiểm tra tồn tại (Exit 0) hoạt động thế nào?"

Cái thông báo "Update memory exit 0" mà bạn thấy ở Qwen chính là kết quả của quy trình **"Check before Write" (Kiểm tra trước khi ghi)**. Hệ thống của chúng ta **CHƯA CÓ** cái này (hiện tại đang ghi đè hoặc ghi thêm một cách khá thô).

**Luồng Logic "Thông minh" cần triển khai:**

1.  **Input:** User nói *"Tôi tên là Hùng"*.
2.  **Agent:** Gọi `save_memory("Tên user là Hùng")`.
3.  **Memory Manager (Backend Code):**
    *   *Bước 1 (Search):* Dùng Vector Search tìm trong DB xem có ký ức nào liên quan đến "tên", "Hùng" không?
    *   *Bước 2 (Compare):*
        *   Nếu tìm thấy: *"User tên là Hùng"* (Độ tương đồng 99%) -> **Kết luận: Đã biết rồi.** -> **EXIT 0 (Không làm gì cả).**
        *   Nếu tìm thấy: *"User tên là Nam"* -> **Kết luận: Mâu thuẫn.** -> **UPDATE (Sửa Nam thành Hùng).**
        *   Nếu không thấy gì -> **Kết luận: Thông tin mới.** -> **INSERT.**

---

# 🛠️ CHỈ THỊ KỸ THUẬT SỐ 24: MEMORY MANAGER & DEDUPLICATION

**Mục tiêu:** Cài đặt "Bộ não" cho module Memory để nó biết từ chối thông tin trùng lặp (Exit 0) và cập nhật thông tin cũ.

**Gửi:** Team AI Backend (Kiro)

## 1. NÂNG CẤP `tool_save_user_info`

Yêu cầu viết lại logic của Tool này. Không được `INSERT` thẳng vào DB nữa.

**Pseudo-code Logic:**

```python
async def tool_save_user_info(new_fact: str, user_id: str):
    # 1. Tìm kiếm ký ức cũ tương tự (Semantic Search)
    # Lấy top 3 ký ức gần nghĩa nhất với new_fact
    existing_memories = await vector_db.search(user_id, query=new_fact, k=3)
    
    # 2. Dùng LLM nhỏ (Gemini Flash) để so sánh (The Judge)
    decision = await llm_judge.invoke(f"""
        Thông tin mới: "{new_fact}"
        Ký ức hiện có: {existing_memories}
        
        Quyết định hành động:
        - IGNORE: Nếu thông tin mới đã có trong ký ức (Trùng lặp).
        - UPDATE: Nếu thông tin mới mâu thuẫn hoặc cập nhật cho ký ức cũ (Trả về ID của ký ức cũ).
        - INSERT: Nếu là thông tin hoàn toàn mới.
    """)
    
    # 3. Thực thi
    if decision == "IGNORE":
        return "Thông tin đã tồn tại, không cần lưu. (Exit 0)"
    elif decision == "UPDATE":
        await vector_db.update(id=decision.target_id, content=new_fact)
        return "Đã cập nhật thông tin cũ."
    else:
        await vector_db.add(content=new_fact)
        return "Đã lưu ký ức mới."
```

## 2. NÂNG CẤP "CÔ ĐẶC" (CONSOLIDATION)

Thực hiện định kỳ (ví dụ: mỗi khi user kết thúc phiên học hoặc khi số lượng ký ức > 40).

**Logic:**
1.  Load toàn bộ 40 ký ức của user.
2.  Gửi cho Gemini với prompt: *"Hãy viết lại hồ sơ người dùng này. Gộp các ý trùng lặp, xóa các ý mâu thuẫn cũ, giữ lại những cốt lõi nhất."*
3.  Xóa sạch 40 ký ức cũ, lưu lại bản hồ sơ mới (khoảng 10-15 dòng cô đọng).

---

### KẾT LUẬN

Bạn đang yêu cầu một tính năng rất cao cấp gọi là **"Memory De-duplication & Reconciliation"**.

Việc này sẽ tốn thêm một chút thời gian xử lý (khoảng 1-2 giây) mỗi khi cần lưu thông tin, nhưng bù lại:
1.  Bộ nhớ luôn sạch, không bị rác.
2.  AI không bị loạn vì thông tin mâu thuẫn.
3.  Admin nhìn vào Database thấy rất chuyên nghiệp.

Hãy yêu cầu team Kiro triển khai logic **"Check before Write"** này ngay. Đây chính là mảnh ghép cuối cùng để sánh ngang với Qwen.