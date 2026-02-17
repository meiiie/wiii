Chào bạn,

Với tư cách là Cố vấn Kiến trúc, tôi đánh giá báo cáo phản hồi của team Kiro là **RẤT TRUNG THỰC VÀ CHI TIẾT (HONEST & DETAILED)**.

Team đã thừa nhận những điểm yếu (như thiếu Eviction Policy, chỉ Deduplicate khi đọc chứ không phải khi ghi) một cách thẳng thắn. Đây là nền tảng tốt để cải tiến.

Dưới đây là **Quyết định Chiến lược** của tôi cho lộ trình tiếp theo.

---

# 🛑 CHỈ THỊ KỸ THUẬT SỐ 22: TỐI ƯU HÓA BỘ NHỚ (MEMORY OPTIMIZATION)

**Người gửi:** Ban Cố vấn Kiến trúc
**Người nhận:** Team AI Backend (Kiro)
**Mức độ:** TRUNG BÌNH (Maintenance & Optimization)

## 1. PHÊ DUYỆT LỘ TRÌNH CẢI TIẾN

Tôi đồng ý hoàn toàn với Roadmap mà team đề xuất:

*   **Phase 1 (Memory Capping):** Triển khai ngay. Giới hạn **50 facts/user**. Xóa FIFO (cũ nhất xóa trước) là đủ tốt.
*   **Phase 2 (True Deduplication):** Triển khai ngay. Việc lưu chồng chất dữ liệu cũ (Append-only) là lãng phí tài nguyên vô ích. Hãy chuyển sang cơ chế **Upsert (Update or Insert)** dựa trên `fact_type`.

## 2. YÊU CẦU BỔ SUNG VỀ API (PHASE 3)

Về API quản lý Memory, chúng ta không cần làm ngay bây giờ vì Frontend chưa có giao diện cho nó. Tuy nhiên, hãy chuẩn bị sẵn Backend.

**Yêu cầu:** Thêm endpoint `GET /api/v1/memories/{user_id}` trả về danh sách các facts dưới dạng JSON sạch đẹp:
```json
[
  {"id": "...", "type": "name", "value": "Minh", "created_at": "..."},
  {"id": "...", "type": "goal", "value": "Học COLREGs", "created_at": "..."}
]
```

## 3. LỜI KHUYÊN CUỐI CÙNG VỀ "ATOMIC FACTS"

Team đang làm rất tốt việc trích xuất "Atomic Facts" (`{fact_type: "name", value: "Minh"}`). Hãy duy trì điều này.

**Lưu ý nhỏ:** Đừng để AI trích xuất quá nhiều `fact_type` vụn vặt. Hãy giới hạn trong khoảng 5-7 loại quan trọng nhất:
*   `name`
*   `role` (Sinh viên/Giáo viên)
*   `level` (Năm 3, Đại phó...)
*   `goal` (Mục tiêu học tập)
*   `preference` (Phong cách học: Thích ví dụ, Thích lý thuyết)
*   `weakness` (Hay quên cái gì)

---

### TỔNG KẾT

Hệ thống Memory của bạn đang ở mức **8/10**.
*   Đã có Atomic Facts (Tốt).
*   Đã có Semantic Search (Tốt).
*   Chỉ thiếu dọn dẹp rác (Garbage Collection).

Hãy cho team triển khai **Phase 1 & 2** ngay trong tuần tới để biến nó thành **10/10**. Sau đó, bạn có thể tự tin tuyên bố hệ thống Memory của mình ngang ngửa các Chatbot thương mại.