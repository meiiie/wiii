Chào bạn,

Với tư cách là Cố vấn Kiến trúc, tôi đánh giá **Architecture Cleanup Report** này là một bản phân tích hiện trạng **RẤT CHÍNH XÁC VÀ TRUNG THỰC**.

Dự án đã phát triển thần tốc từ một Prototype lên Production chỉ trong vài tuần, nên việc tích tụ nợ kỹ thuật (Tech Debt) như thư mục `scripts/` hỗn độn hay file `semantic_memory.py` phình to là điều dễ hiểu.

Bây giờ là thời điểm vàng để dọn dẹp trước khi chúng ta bước vào giai đoạn mở rộng tiếp theo.

Dưới đây là **Quyết định Chiến lược** của tôi dựa trên báo cáo này.

---

# 🧹 CHỈ THỊ KỸ THUẬT SỐ 25: CLEANUP & REFACTORING

**Người gửi:** Ban Cố vấn Kiến trúc
**Người nhận:** Team AI Backend (Kiro)
**Mục tiêu:** Chuẩn hóa cấu trúc dự án, loại bỏ mã chết, chuẩn bị cho khả năng mở rộng.

## 1. PHÊ DUYỆT KẾ HOẠCH DỌN DẸP (APPROVED PLAN)

Tôi đồng ý hoàn toàn với đề xuất `Proposed Directory Restructure` của team.

### A. Dọn dẹp thư mục `scripts/` (Ưu tiên P0)
*   **Hành động:** Di chuyển ngay lập tức 45+ file test từ `scripts/` sang cấu trúc `tests/` chuẩn (e2e, integration, unit).
*   **Lợi ích:** Giúp CI/CD chạy test tự động dễ dàng, admin không bị rối mắt khi vào thư mục scripts.

### B. Loại bỏ Legacy Code (Ưu tiên P1)
*   **Hành động:** Kiểm tra file `chat_service.py`. Nếu `UnifiedAgent` đã hoạt động ổn định (đã qua kiểm thử v0.7), hãy mạnh dạn **XÓA BỎ** (hoặc move vào thư mục `archive/`) các file:
    *   `app/engine/agents/chat_agent.py`
    *   `app/engine/graph.py` (Phần IntentClassifier cũ)
*   **Nguyên tắc:** "Less code is better code". Đừng giữ lại mã thừa gây nhiễu loạn cho người mới.

### C. Refactor `semantic_memory.py` (Ưu tiên P2)
*   **Hành động:** Tách file 1,298 dòng này thành package `app/engine/semantic_memory/`:
    *   `__init__.py` (Export facade)
    *   `core.py` (Logic chính)
    *   `context.py` (Lắp ghép context)
    *   `extraction.py` (Trích xuất fact)
*   **Lợi ích:** Dễ đọc, dễ test từng phần nhỏ.

---

## 2. QUYẾT ĐỊNH VỀ CÁC VẤN ĐỀ KHÁC

*   **Guardrails vs GuardianAgent:** Đồng ý giữ cả hai. Mô hình "Layered Defense" (Phòng thủ nhiều lớp) là chuẩn mực bảo mật. Rule-based chặn nhanh cái thô thiển, LLM chặn cái tinh vi.
*   **Memory Components:** Đồng ý giữ nguyên cấu trúc các module nhỏ (`memory_manager`, `consolidator`...). Chúng đang làm tốt nhiệm vụ Single Responsibility.
*   **Documentation:** Yêu cầu gộp các file `SEMANTIC_MEMORY_vX.md` thành một file duy nhất `SEMANTIC_MEMORY_ARCHITECTURE.md` có mục Version History. Xóa các file cũ để tránh nhầm lẫn.

---

## 3. LỆNH TRIỂN KHAI

Bạn hãy chuyển chỉ thị này cho Kiro và yêu cầu thực hiện theo thứ tự ưu tiên:

1.  **Tuần này:** Hoàn thành mục A (Di chuyển Script/Test) và B (Xóa Legacy Code).
2.  **Tuần sau:** Thực hiện mục C (Tách file Memory).

**Thông điệp cho team:**
> "Chúng ta không chỉ viết code chạy được, chúng ta viết code để sống lâu dài. Hãy dành 2 ngày tới để dọn nhà sạch sẽ trước khi đón khách mới."

Chúc team dọn dẹp thành công! Một codebase sạch sẽ là niềm tự hào của kỹ sư. 🧹✨