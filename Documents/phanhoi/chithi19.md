Chào bạn,

Rất tốt. Bạn đã có Connection String chuẩn (Pooled) của Neon.

Tuy nhiên, **LƯU Ý KỸ THUẬT QUAN TRỌNG:**
Connection string bạn nhận được là chuẩn `libpq`. Trong code Python của chúng ta (sử dụng `SQLAlchemy` + `asyncpg`), team cần **thêm prefix** `+asyncpg` vào đầu URL để driver hoạt động đúng.

Dưới đây là **Chỉ thị Kỹ thuật số 19** để bạn chuyển cho team. Nó bao gồm việc chuyển đổi Database và sửa lại cơ chế Health Check để bảo vệ tài khoản Neon Free.

---

# 🛠️ CHỈ THỊ KỸ THUẬT SỐ 19: MIGRATION TO NEON & TỐI ƯU HEALTH CHECK

**Người gửi:** Ban Cố vấn Kiến trúc
**Người nhận:** Team AI Backend (Kiro)
**Mức độ:** TỐI MẬT / KHẨN CẤP (Critical Infrastructure Change)

## 1. MỤC TIÊU
1.  Chuyển Database từ Supabase sang **Neon (Serverless Postgres)** để khắc phục vĩnh viễn lỗi `MaxClients`.
2.  Điều chỉnh API Health Check để **tránh làm cạn kiệt** 100 giờ Compute miễn phí của Neon (do Cronjob ping liên tục).

---

## 2. CẤU HÌNH DATABASE MỚI (NEON)

Yêu cầu team cập nhật biến môi trường `DATABASE_URL` trên cả Local và Render với giá trị sau:

**Connection String (Đã tối ưu cho Python/Asyncpg):**
```text
postgresql+asyncpg://neondb_owner:npg_lrbpiOCkm98Y@ep-quiet-bush-a1uuhk24-pooler.ap-southeast-1.aws.neon.tech/neondb?ssl=require
```

*Lưu ý cho Dev:*
*   Đã thêm `+asyncpg` vào scheme.
*   Đã bỏ `channel_binding=require` (đôi khi gây lỗi với một số phiên bản driver, chỉ giữ `ssl=require` là đủ an toàn và tương thích).
*   Đây là **Pooled Connection**, nên `pool_size` trong code có thể tăng lên 5-10 thoải mái, không cần dè sẻn như Supabase.

---

## 3. QUY TRÌNH MIGRATION (CÀI ĐẶT LẠI TỪ ĐẦU)

Vì đây là Database mới tinh, yêu cầu thực hiện các bước sau:

1.  **Init Schema:** Chạy lệnh Alembic để tạo bảng.
    ```bash
    alembic upgrade head
    ```
2.  **Enable Vector:** Chạy lệnh SQL trực tiếp vào Neon (qua SQL Editor trên web hoặc code):
    ```sql
    CREATE EXTENSION IF NOT EXISTS vector;
    ```
3.  **Re-ingest Data:** Chạy lại script nạp dữ liệu để tạo lại Knowledge Graph và Embeddings.
    ```bash
    python scripts/import_colregs.py
    # Và các script import khác nếu có
    ```

---

## 4. SỬA ĐỔI CHIẾN LƯỢC HEALTH CHECK (RẤT QUAN TRỌNG)

Để bảo vệ Neon không bị "thức" 24/7 bởi Cronjob (gây tốn tiền/hết quota), yêu cầu sửa file `app/api/v1/health.py`:

### A. Endpoint `/health` (Dành cho Cronjob/Render Ping)
*   **Logic:** Chỉ trả về static JSON. **TUYỆT ĐỐI KHÔNG** kết nối Database.
*   **Mục đích:** Giữ cho Server Python (Render) không ngủ, nhưng cho phép Database (Neon) ngủ khi không có user.

```python
@router.get("/health")
async def health_check_shallow():
    # Shallow check - No DB Access
    return {"status": "ok", "service": "maritime-ai-tutor"}
```

### B. Endpoint `/api/v1/health/db` (Dành cho Debug/Admin)
*   **Logic:** Thực hiện query `SELECT 1` vào Neon.
*   **Mục đích:** Chỉ dùng khi Dev cần kiểm tra kết nối bằng tay.

```python
@router.get("/api/v1/health/db")
async def health_check_deep():
    # Deep check - Wakes up Neon DB
    # ... logic check db cũ chuyển vào đây ...
    return {"status": "ok", "database": "connected"}
```

---

## 5. CẬP NHẬT CRONJOB

*   Đảm bảo dịch vụ UptimeRobot/Cron-job đang ping vào đường dẫn: `https://maritime-ai-chatbot.onrender.com/health` (Cái Shallow check).
*   **Không được** ping vào `/api/v1/health/db`.

---

### KẾT LUẬN

Sau khi thực hiện chỉ thị này:
1.  Lỗi kết nối sẽ biến mất (nhờ Neon Pooling).
2.  Hệ thống sẽ chạy miễn phí vĩnh viễn (Render luôn thức, Neon ngủ khi rảnh).
3.  Dữ liệu sẽ được làm mới sạch sẽ.

**Yêu cầu:** Triển khai ngay lập tức và báo cáo lại khi đã Ingest xong dữ liệu trên Neon.