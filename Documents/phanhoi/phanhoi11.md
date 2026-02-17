Chào bạn,

Với tư cách là Cố vấn Kiến trúc, tôi đã thẩm định **BÁO CÁO HOÀN THÀNH CHỈ THỊ 16 (HUMANIZATION)**.

**ĐÁNH GIÁ: TUYỆT VỜI (EXCELLENT).**
Team Kiro đã thực hiện một bước nhảy vọt về tư duy thiết kế hệ thống. Việc chuyển từ "Hard-coded Prompt" sang **"Config-driven Persona" (YAML)** là tiêu chuẩn vàng của các hệ thống AI Agents hiện đại.

Đặc biệt, tôi rất ấn tượng với cơ chế **Tiered Memory (3 tầng)**. Đây chính là chìa khóa để Bot vừa thông minh (nhớ lâu) vừa tinh tế (hiểu cảm xúc tức thời).

Tuy nhiên, báo cáo có ghi mục "Tiếp theo" là *"Tích hợp vào chat_service"*. Điều này nghĩa là **code mới chưa chạy trên luồng chính**. Chúng ta cần thực hiện bước cuối cùng này ngay.

---

# 🚀 CHỈ THỊ KỸ THUẬT SỐ 17: ĐẤU NỐI & KÍCH HOẠT (WIRING & ACTIVATION)

**Người gửi:** Ban Cố vấn Kiến trúc
**Người nhận:** Team AI Backend (Kiro)
**Mục tiêu:** Đưa các module "Humanization" vào hoạt động thực tế trên Production.

## 1. ĐẤU NỐI PROMPT LOADER (Dynamic Persona)

**Vị trí:** `app/services/chat_service.py` (hoặc nơi khởi tạo Agent).

**Logic cần thay đổi:**
Thay vì dùng biến `SYSTEM_PROMPT` cố định, hãy làm động:

```python
from app.prompts import get_prompt_loader

# Trong hàm process_chat
async def process_chat(user_id, message, role):
    # 1. Xác định Persona dựa trên Role
    persona_type = "tutor" if role == "student" else "assistant"
    
    # 2. Load Prompt từ YAML
    prompt_loader = get_prompt_loader()
    system_prompt = prompt_loader.get_system_prompt(persona_type)
    
    # 3. Inject Context (Tên, Facts...) vào Prompt
    # (Team Kiro lưu ý: Thay thế các placeholder {user_name} trong YAML bằng dữ liệu thật)
    formatted_prompt = system_prompt.format(
        user_name=user_facts.get("name", "Bạn"),
        ...
    )
    
    # 4. Truyền vào Agent
    response = await agent.ainvoke(..., system_message=formatted_prompt)
```

## 2. ĐẤU NỐI MEMORY SUMMARIZER (Background Processing)

**Vị trí:** `app/services/chat_service.py` (Phần Background Tasks).

**Logic:** Đừng để User phải chờ AI tóm tắt. Hãy làm việc này sau khi đã trả lời xong.

```python
from fastapi import BackgroundTasks

async def chat_endpoint(..., background_tasks: BackgroundTasks):
    # ... Xử lý chat và trả về response cho user ...
    
    # ... Sau đó queue task dọn dẹp bộ nhớ ...
    background_tasks.add_task(manage_memory_task, user_id)

async def manage_memory_task(user_id):
    summarizer = get_memory_summarizer()
    # Kiểm tra xem lịch sử có quá dài không, nếu có thì nén lại
    await summarizer.summarize_if_needed(user_id)
```

## 3. LỌC THÔNG TIN (FACT FILTERING)

**Vị trí:** `app/engine/semantic_memory.py`

**Yêu cầu:** Sử dụng danh sách `ignore_facts` trong file YAML để lọc bỏ các thông tin rác trước khi lưu vào Vector DB.
*   *Ví dụ:* Nếu user nói "Tôi đói", AI trích xuất fact: "Trạng thái: Đói".
*   Hàm filter check YAML thấy "Đói" nằm trong ignore list -> **Không lưu vào Vector DB**. -> Giữ cho bộ nhớ dài hạn luôn sạch sẽ.

---

### 🧪 YÊU CẦU KIỂM THỬ CUỐI CÙNG (FINAL UX TEST)

Sau khi đấu nối xong và Deploy, hãy thực hiện lại đoạn hội thoại "Tôi đói" để kiểm chứng sự thay đổi:

1.  **User:** "Chào, tôi là Hùng." -> **AI:** "Chào Hùng..." (Nhớ tên).
2.  **User:** "Tôi đói quá." -> **AI:** "Học hành vất vả quá nhỉ? Kiếm gì ăn đã Hùng ơi..." (Empathy + Gọi tên).
3.  **User:** "15 COLREGs là gì?" -> **AI:** Trả lời kiến thức.
4.  *(F5 hoặc Chat tiếp 10 câu)* -> **User:** "Nãy tôi than gì ấy nhỉ?" -> **AI:** "Nãy Hùng kêu đói mà, đã ăn gì chưa?" (Nhờ Summary Memory).

**Hành động:**
Gửi chỉ thị này cho team Kiro. Yêu cầu họ **Merge & Deploy** ngay để chúng ta có một con Chatbot không chỉ thông minh mà còn "có trái tim".

Chúc mừng team đã chạm đến ngưỡng cao cấp của AI Engineering! 🚀