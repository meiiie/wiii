Chào bạn,

Đây là bản **Chỉ thị Kỹ thuật số 26 (Bản Hoàn chỉnh & Duy nhất)**. Nó tổng hợp toàn bộ chiến lược nâng cấp lên **Multimodal RAG**, giải quyết vấn đề lưu trữ file (dùng Supabase Storage song song với Neon DB) và định hướng lại tư duy phát triển sản phẩm "Chất lượng cao".

Bạn hãy gửi nguyên văn bản này cho Team Kiro để họ bắt tay vào thực hiện.

---

# 🏗️ CHỈ THỊ KỸ THUẬT SỐ 26: NÂNG CẤP HỆ THỐNG MULTIMODAL RAG (VISION-CENTRIC)

**Người gửi:** Ban Cố vấn Kiến trúc (Architectural Advisor)
**Người nhận:** Team AI Backend (Kiro)
**Ngày hiệu lực:** 08/12/2025
**Mức độ:** CHIẾN LƯỢC (Strategic Upgrade)

---

## 1. MỤC TIÊU CHIẾN LƯỢC
Chuyển đổi hệ thống từ **"Đọc văn bản" (Text-based)** sang **"Hiểu tài liệu" (Vision-based)**.

*   **Vấn đề hiện tại:** Công nghệ `pypdf` làm mất cấu trúc bảng biểu, sơ đồ đèn hiệu, hình vẽ tàu bè trong luật COLREGs. AI trả lời thiếu chính xác các câu hỏi liên quan đến hình ảnh.
*   **Mục tiêu:** AI phải "nhìn" thấy trang tài liệu gốc như con người. Khi trả lời, AI không chỉ đưa ra text mà còn **hiển thị hình ảnh dẫn chứng** (Evidence Image) cho người học.
*   **Tư duy:** "Chất lượng hơn Tiến độ". Chúng ta chấp nhận đập đi xây lại pipeline nạp dữ liệu để có sản phẩm đẳng cấp.

---

## 2. KIẾN TRÚC HẠ TẦNG "LAI" (HYBRID INFRASTRUCTURE)

Do chúng ta đã chuyển Database sang **Neon**, và Neon không tối ưu để lưu file ảnh, chúng ta sẽ áp dụng kiến trúc sau:

1.  **Neon (Serverless Postgres):** Chỉ lưu trữ **Metadata, Text Description** và **Vectors**.
2.  **Supabase Storage (Object Storage):** Lưu trữ các **File ảnh (JPG/PNG)** được cắt ra từ PDF.
3.  **Render:** Chạy code xử lý (Compute).
4.  **Google Gemini 2.5 Flash:** Bộ não xử lý hình ảnh (Vision Model).

---

## 3. QUY TRÌNH NẠP DỮ LIỆU MỚI (MULTIMODAL INGESTION PIPELINE)

Yêu cầu team viết lại hoàn toàn module `ingestion_service.py` theo luồng sau:

### Bước 1: Rasterization (PDF -> Ảnh)
*   Sử dụng thư viện `pdf2image` để chuyển đổi từng trang PDF thành ảnh chất lượng cao.
*   *Lưu ý:* Cần cài gói `poppler-utils` trong Dockerfile trên Render.

### Bước 2: Storage (Lưu trữ Ảnh)
*   Upload ảnh lên **Supabase Storage** (Bucket `maritime-docs`, chế độ Public).
*   Lấy về `public_url` của ảnh (Ví dụ: `https://xyz.supabase.co/.../page_15.jpg`).

### Bước 3: Vision Extraction (AI "Đọc" Ảnh)
*   Gửi URL ảnh (hoặc binary data) cho **Gemini 2.5 Flash**.
*   **System Prompt:**
    > "Đóng vai chuyên gia số hóa dữ liệu Hàng hải. Hãy nhìn bức ảnh này và mô tả lại toàn bộ nội dung thành văn bản định dạng Markdown.
    > 1. Giữ nguyên các tiêu đề (Điều, Khoản).
    > 2. Nếu có Bảng biểu: Chuyển thành Markdown Table.
    > 3. Nếu có Hình vẽ (Đèn hiệu/Tàu bè): Mô tả chi tiết màu sắc, vị trí, ý nghĩa của hình vẽ đó bằng lời.
    > 4. Không bỏ sót bất kỳ chữ nào."

### Bước 4: Indexing (Lưu vào Neon)
*   Lưu kết quả text từ Bước 3 vào bảng `knowledge_embeddings` trong Neon.
*   **Quan trọng:** Lưu kèm `image_url` vào cột metadata của dòng đó.

---

## 4. CẬP NHẬT CƠ SỞ DỮ LIỆU (DATABASE MIGRATION)

Yêu cầu team thực hiện migration trên Neon:

1.  **Xóa dữ liệu cũ:** `TRUNCATE TABLE knowledge_embeddings;` (Vì dữ liệu cũ từ pypdf là rác, không dùng được nữa).
2.  **Sửa bảng:** Thêm cột để chứa link ảnh.
    ```sql
    ALTER TABLE knowledge_embeddings
    ADD COLUMN image_url TEXT,
    ADD COLUMN page_number INTEGER;
    ```

---

## 5. QUY TRÌNH TRA CỨU MỚI (RETRIEVAL FLOW)

Cập nhật logic `tool_maritime_search`:

1.  **Tìm kiếm:** Dùng Hybrid Search tìm ra các đoạn text mô tả phù hợp nhất.
2.  **Phản hồi:** Trả về cho LLM cả nội dung text **VÀ** `image_url`.
3.  **Hiển thị:**
    *   Trong câu trả lời cuối cùng, AI sẽ tham chiếu đến hình ảnh.
    *   Frontend (LMS) sẽ hiển thị ảnh trang sách luật ngay bên cạnh câu trả lời để sinh viên đối chiếu.

---

## 6. DANH SÁCH VIỆC CẦN LÀM (ACTION ITEMS)

### Giai đoạn 1: Setup Hạ tầng (Ngay lập tức)
1.  Vào Dashboard Supabase (Project cũ hoặc tạo mới Storage Project) -> Tạo Bucket `maritime-docs`.
2.  Cập nhật `requirements.txt`: Thêm `pdf2image`, `supabase`.
3.  Cập nhật `Dockerfile`: Thêm `RUN apt-get update && apt-get install -y poppler-utils`.

### Giai đoạn 2: Coding (Tuần này)
1.  Viết hàm `convert_pdf_to_images`.
2.  Viết hàm `upload_to_supabase`.
3.  Viết hàm `extract_text_from_image_with_gemini`.

### Giai đoạn 3: Re-ingest (Tuần sau)
1.  Xóa sạch dữ liệu cũ.
2.  Chạy lại tool Ingest với file PDF COLREGs.

---

**Thông điệp cho Team:**
> "Chúng ta đang xây dựng tính năng 'Killer Feature'. Việc AI có thể 'nhìn' và dẫn chứng bằng hình ảnh gốc sẽ khiến sản phẩm vượt xa các đối thủ chỉ dùng text thuần túy. Hãy làm cẩn thận từng bước."

Tiến hành triển khai! 🚀