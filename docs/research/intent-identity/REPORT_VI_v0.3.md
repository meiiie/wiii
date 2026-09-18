# Báo cáo nghiên cứu v0.3

**Exactly-Once Effects for Re-Planning LLM Agents: A Reduction, a Retention Hazard, and an Evidence Contract**
(tên cũ: *Intent Identity and Exactly-Once Effects for Non-Deterministic LLM Agents*)

Ngày: 19 tháng 9 năm 2026. Trạng thái: kết quả phát triển đã chạy; tái lập độc lập; chưa nộp.

## 1. Quyết định điều hành sau đợt v0.3

Đợt v0.2 kết thúc với một kết quả âm: đối chứng mạnh dùng khóa ổn định theo nghĩa vụ hòa với bộ xác minh trong mọi miền đã thử. Báo cáo v0.2 mục 7 đặt điều kiện tiếp theo: *tìm được một vấn đề thực mà đối chứng tốt chưa giải quyết*. Đợt này đã tìm được vấn đề đó, và nó không phải là một giả thiết do ta dựng lên mà là **điều khoản hợp đồng đã được nhà cung cấp công bố**:

- Stripe xóa khóa idempotency sau ít nhất 24 giờ và "tạo yêu cầu mới nếu khóa được dùng lại sau khi bản gốc đã bị xóa".
- Amazon SQS FIFO chỉ chống lặp trong cửa sổ 5 phút.

Giả thiết nền của phép quy giản trong v0.2 ("sink giữ khóa trong toàn bộ quá trình khôi phục") vì thế **không phải điều nhà cung cấp cam kết**. Khi khôi phục diễn ra sau cửa sổ (mất điện dài, khôi phục checkpoint muộn), mọi chính sách retry-cùng-khóa, kể cả đối chứng mạnh và bộ xác minh v0.2, đều tạo hiệu ứng lặp. Đây là kết quả trung tâm của v0.3 và đã được chứng minh, vét cạn, kiểm tra mô hình và chạy tiến trình thật.

Quyết định: giữ nguyên kết quả âm v0.2 ở vị trí trung tâm (nay được tái lập độc lập), viết lại đóng góp quanh **ranh giới của phép quy giản** và **hai hợp đồng nằm ngoài ranh giới đó** (cửa sổ giữ khóa và bằng chứng kết quả). Chưa nộp. Chưa gọi model. Chưa gọi API thương mại.

## 2. Đã làm gì trong đợt này

### 2.1. Tái lập độc lập toàn bộ v0.2

Mã nguồn v0.2 không có trong phiên này; artifact v0.3 được viết mới hoàn toàn từ đặc tả trong bản thảo v0.2 (Python thư viện chuẩn + SQLite). Điều này đồng thời giải quyết mối đe dọa "cùng mã, cùng nhóm" mà v0.2 nêu ở mục IX.B.

| Hạng mục | v0.2 | v0.3 (tái lập độc lập) | Khớp |
| --- | --- | --- | --- |
| D1 số trường hợp | 186.674 | 186.674 | có |
| D1 lặp của khóa theo nhóm (G) | 130.348 (16 / 1.308 / 129.024) | 130.348 (16 / 1.308 / 129.024) | chính xác |
| D1 R và V | 0 lặp, 0 sai khác | 0 lặp, 0 sai khác | có |
| E1 | 65.535 tập; 1.048.560 phép kiểm; 941 tập có frontier khác rỗng | giống hệt | chính xác |
| E3 | công thức khớp oracle đến n = 8 | khớp đến n = 10 (mở rộng) | có |
| I1 | 240/240 | 240/240 | có |
| I2 | 24/24 | 24/24 | có |
| M1 | 480 trạng thái / 1.266 chuyển | 1.180 / 3.467 (mã hóa khác) | cùng dạng phản ví dụ; số không so sánh được |

Điểm bổ sung quan trọng: đối chứng được **làm mạnh thêm** thành `R+` (tham chiếu sổ cái của chính nó trước khi gửi). `R+` hòa `V` cả về vector hiệu ứng lẫn số lời gọi sink (372.145 so với 744.290 của `R` cũ). Kết quả âm v0.2 vì thế còn sắc hơn: bộ xác minh không tiết kiệm được gì so với một đối chứng chịu đọc sổ cái của mình.

Số 1.061 − 1.056 = 5 lời gọi dư trong v0.2 mà đánh giá trước đã hỏi: trong v0.3, số lời gọi dư đúng bằng số lượt retry sau mất xác nhận (120 = 60 + 60 lượt ở hai điểm lỗi "sau hiệu ứng, trước xác nhận"), tất cả được provider trả lời bằng receipt đã lưu. Con số 5 của v0.2 chưa giải thích được từ đặc tả và cần đối chiếu với mã gốc.

### 2.2. Kết quả mới: cửa sổ giữ khóa hữu hạn

**Định nghĩa.** Profile `P_D(T)`: sink chống lặp theo khóa trong ít nhất `T` kể từ lần commit đầu; sau đó khóa có thể bị xóa và yêu cầu cùng khóa có thể commit lần nữa. Stripe là `P_D(T ≥ 24h)`; SQS FIFO là `P_D(T = 5 phút)`.

**Mệnh đề 3 (retry cùng khóa dưới cửa sổ hữu hạn).** Nếu controller ghi bền thời điểm giữ `h(ω)` trước khi truyền, và độ lệch đồng hồ cộng độ trễ mạng bị chặn bởi `δ`, thì retry cùng khóa tại thời điểm `t` an toàn trong mọi lịch sử phù hợp với tri thức của controller **khi và chỉ khi** `t < h(ω) + T − δ`. Quyết định này chỉ cần sổ cái của controller và tham số hợp đồng `T`; **không truy vấn sink nào thay thế được nó**, vì tra cứu âm sau khi khóa bị xóa phù hợp với cả hai lịch sử.

**Hệ quả.** Sau cửa sổ, `P_D(T)` xuống cấp thành `P_F` (nếu có fence hoặc bằng chứng) hoặc `P_O`. Controller nhận biết cửa sổ = controller khóa ổn định + bước xuống cấp này: bằng chứng dương thì xác nhận; có fence thì cấp khóa mới; không có gì thì chuyển sang trạng thái `unresolved` (an toàn, chưa hoàn thành).

**Bằng chứng đã chạy:**

| Nghiên cứu | Kết quả |
| --- | --- |
| D1-TTL (186.674 trường hợp × 3 trạng thái tại lúc crash) | Khi index chống lặp đã bị xóa và xác nhận bị mất: `R`, `R+`, `V` lặp trong **toàn bộ 149.217** trường hợp có tiền tố đã commit. Chính sách nhận biết cửa sổ `Vr`: 0 lặp. `Vr+E` (có tra cứu): 0 lặp, 0 chưa hoàn thành. |
| M1, mutant mới "retry sau khi hết cửa sổ" | Phản ví dụ 7 bước: hold, send, commit, crash, hết cửa sổ, resend cùng khóa, commit. Cấu hình an toàn có thêm chuyển trạng thái hết cửa sổ vẫn duyệt hết 1.396 trạng thái không vi phạm. |
| I4 (80 lượt tiến trình thật, provider có TTL 0,5 s, khôi phục sau 0,8 s) | Retry ngây thơ sau mất xác nhận: lặp **20/20** (cả R và V). Khôi phục nhận biết cửa sổ: lặp 0/40; có endpoint tra cứu thì hoàn thành 10/10; không có thì `unresolved` 10/10. |

### 2.3. Kết quả mới: tiếp quản khi yêu cầu cũ còn đang bay (I3)

Đánh giá v0.2 chỉ ra I2 (ba worker đua) không bao giờ chạm tới cơ chế chống lặp của provider vì reservation ở controller đã phân xử. Đo lại trong v0.3: **0/96** lời gọi sink trong I2 là dedup. Vì thế thiết kế thêm I3: worker A bị SIGKILL 150 ms sau khi gửi trong khi provider cố tình trễ commit; worker B tiếp quản slot đang `held` sau khi lease hết.

| Profile | Khôi phục | Lặp (trên 5) | Cơ chế |
| --- | --- | --- | --- |
| P_D | ngây thơ / nhận biết | 0 / 0 | dedup của sink (yêu cầu cũ tới sau → receipt) |
| P_F | ngây thơ | 5 | không có |
| P_F | nhận biết | 0 | fence chặn yêu cầu cũ → khóa mới; hoặc fence trả receipt |
| P_O | ngây thơ | 5 | không có |
| P_O | nhận biết, sớm | 0 (5 `unresolved`) | dừng lại; 0,5 s sau thế giới đã hoàn thành mà controller không biết |
| P_O | nhận biết, muộn | 0 | tra cứu dương → xác nhận |

Ba cơ chế cần thiết (dedup của sink, fence-rồi-khóa-mới, trạng thái `unresolved` tường minh) xuất hiện thành ba dòng đo được, thay vì chỉ là văn xuôi.

### 2.4. Kết quả mới: lớp ngữ nghĩa batch quyết định tập niềm tin (E4)

Nguồn của "tương quan" trong v0.2 mục V hóa ra không hề lạ: đó là **cách provider xử lý một yêu cầu batch** mà phản hồi đã mất. Nếu journal ghi thành viên, thứ tự và lớp xử lý của yêu cầu, tập niềm tin được xác định hoàn toàn:

| Lớp | Tập đã hoàn thành khả dĩ | Kỳ vọng số truy vấn tối ưu | Journal ba trạng thái |
| --- | --- | --- | --- |
| độc lập (SQS batch, SES bulk) | mọi tập con | n | n |
| nguyên tử (một yêu cầu Stripe) | ∅ hoặc tất cả | 1 | n |
| tiền tố (xử lý tuần tự, dừng khi lỗi) | các tiền tố | ⌈log₂(n+1)⌉ − (2^⌈log₂(n+1)⌉ − (n+1))/(n+1); n = 8 → 3,22 | n |
| đúng k (tổng hợp đáng tin) | các k-tập | công thức v0.2; n = 8, k = 4 → 6,4 | n |

Oracle động quy hoạch chính xác khớp mọi công thức đóng đến n = 10. Chi phí giữ thông tin này: một trường mỗi yêu cầu.

**Đã kiểm chứng trên runtime (I5, 68 lượt):** worker gửi một yêu cầu batch rồi bị SIGKILL trước khi đọc phản hồi; provider làm lỗi các entry theo "thế giới" được chọn; mọi thế giới của mỗi lớp đều được chạy một lần. Successor khôi phục từ journal ba trạng thái hoặc journal có cấu trúc:

| Lớp / n | Journal ba trạng thái (probe TB) | Journal có cấu trúc (probe TB) | Oracle E4 |
| --- | --- | --- | --- |
| độc lập / 4 | 4,00 | 4,00 | 4,00 |
| nguyên tử / 4 | 4,00 | 1,00 | 1,00 |
| tiền tố / 4 | 4,00 | 2,40 | 2,40 |
| tiền tố / 8 | 8,00 | 3,22 | 3,22 |
| nguyên tử / 8 | 8,00 | 1,00 | 1,00 |

Toàn bộ 68 lượt đều exactly-once và hoàn thành đủ (entry vắng mặt được gửi lại bằng khóa mới sau khi đã xác định thế giới). Số probe đo được trùng khớp kỳ vọng của oracle ở mọi ô. Kết luận vẫn giữ đúng phạm vi: thông tin bị bỏ đi bởi phép chiếu ba trạng thái, không phải mọi journal ba trạng thái đều không thể mở rộng.

## 3. Đóng góp được viết lại như thế nào

Không được viết: "Bộ xác minh của chúng tôi vượt idempotency." Câu đúng bây giờ:

1. Khóa nghĩa vụ ổn định là đủ cho exactly-once của agent đổi kế hoạch **đúng chừng nào sink còn giữ khóa**; tái lập độc lập xác nhận bộ xác minh không thêm gì dưới giả thiết đó.
2. Sink thương mại **giới hạn** thời gian giữ khóa. Ngoài giới hạn, cùng những chính sách ấy lặp trong mọi trường hợp mất xác nhận; quyết định an toàn chỉ phụ thuộc vào thời điểm giữ của chính controller và cửa sổ đã công bố.
3. Hoàn thành sau cửa sổ phụ thuộc vào hợp đồng bằng chứng, và chi phí của nó được quyết định bởi thứ journal đã giữ về yêu cầu bị mất.

Đây là đóng góp hệ thống hẹp nhưng thật: **ba trường hợp hợp đồng mà một adapter tool phải khai báo** (`T`, khả năng tra cứu/fence, lớp batch) và hành vi controller đúng cho từng trường hợp.

## 4. Ý nghĩa với Wiii

`docs/architecture/WIII_WORKBENCH_IDENTITY_AND_ACP.md` quy định sau `continuityLevel: recovered`, các mutation bị ngắt giữ trạng thái `unknown outcome` và không tự retry. Đó chính là hành vi `P_O`-aware trong nghiên cứu này: an toàn, nhưng bỏ phí phần hoàn thành mà một tra cứu có thể khôi phục (I3 "muộn", I4 "có lookup": 100% hoàn thành mà không lặp). Ngược lại, một controller retry cùng idempotency key mà không kiểm `h(ω) + T` **không** exactly-once với Stripe hoặc SQS FIFO sau một sự cố dài hơn cửa sổ.

`specs/941-neko-durable-runtime` (user story 3, retry theo request ID không gây tác dụng phụ kép) là trường hợp `P_D` nội bộ; nghiên cứu này bàn về ranh giới với provider bên ngoài phía sau đó. Khi tích hợp, trường hợp đồng cần thêm vào adapter: `idempotency_window_seconds`, `evidence: lookup | fence | none`, `batch_class: independent | atomic | prefix | count`.

## 5. Giới hạn và điều chưa làm

- Không có trace LLM thật; tần suất agent đổi nhóm/đổi kế hoạch chưa đo.
- Không gọi provider thương mại; sự kiện hết cửa sổ được mô phỏng bằng TTL 0,5 s trên sink loopback. Điều khoản Stripe/SQS được trích từ tài liệu chính thức ngày truy cập và có thể thay đổi.
- Lớp "tiền tố" được neo vào chính worker tuần tự của artifact và vào các bộ xử lý tuần tự dừng-khi-lỗi nói chung; chưa xác minh một API batch thương mại cụ thể có ngữ nghĩa này.
- Fence và endpoint bằng chứng là cài đặt của chúng ta cho các khả năng đã được tài liệu hóa, không phải endpoint của nhà cung cấp.
- I3/I4 dựa trên sleep; xác định trong môi trường này với 5 lần lặp mỗi ô; là minh chứng cơ chế, không phải đo tần suất.
- Số trạng thái M1 khác v0.2 vì mã hóa khác; chỉ dạng phản ví dụ là so sánh được.
- Đặc tả các preprint arXiv 2026 (ACRFence, CapLease, AID-Guard, Cordon, PCA) được kế thừa từ audit tài liệu v0.2 và **phải được người kiểm tra lại** trước khi nộp.
- Đối chứng và bộ xác minh dùng chung tầng lưu trữ/truyền tải trong runtime; nghiên cứu vét cạn trừu tượng tồn tại song song vì lý do này.

## 6. Gói bàn giao

- `paper/main.tex`, `paper/main.pdf`: bản thảo v0.3, IEEEtran, 8 trang, 7 bảng, 1 hình TikZ, 15 tài liệu tham khảo (6 nguồn tài liệu nhà cung cấp mới có URL và ngày truy cập).
- `artifact/`: mã (7 module), 29 kiểm thử kernel, 5 driver thí nghiệm, `run_all.py` tái lập toàn bộ (~12 phút), kết quả thô: 472 lượt tiến trình với mã trả về, marker crash, tóm tắt successor và số đếm phía provider; các phép liệt kê vét cạn; witness của bộ duyệt mô hình.
- `PROVIDER_CONTRACTS.md`: trích dẫn nguyên văn có ngày.
- `EVIDENCE_SUMMARY_v0.3.json`: mọi con số trong bài dưới dạng máy đọc.

Không có model weights, API key, chi phí inference, thay đổi sản xuất hay bài nộp nào.

## 7. Cổng đánh giá tiếp theo

1. **Xác thực cửa sổ với tài khoản sandbox** của một provider `P_D(T)` (Stripe test mode): tạo object với khóa, chờ quá cửa sổ, dùng lại khóa, đọc kết quả. Không tốn tiền hiệu ứng thật. Đây là bước biến "điều khoản đã công bố" thành "hành vi đã quan sát".
2. **Ba adapter, ba profile**: kiểm tra bộ trường hợp đồng (`T`, evidence, batch_class) đủ để controller chọn đúng nhánh khôi phục cho Stripe (`P_D(T)` + lookup), SQS FIFO (`P_D(T)` không lookup), Slack (`P_O` + history có rate limit).
3. **Một provider có lớp batch khác "độc lập"** để kiểm chứng giá trị của journal có cấu trúc trên hợp đồng thật.
4. **Thu thập đề xuất LLM tự nhiên** tách khỏi biến đổi cưỡng bức; giữ prompt, phiên bản model, cấu hình sinh và toàn bộ output lỗi.
5. Nếu cả (1) và (3) đạt: bộ trường hợp đồng runtime trở thành sản phẩm bàn giao. Nếu không: giữ là nghiên cứu tái lập / kết quả âm kèm một mối nguy đã được ghi nhận.

Về mục tiêu A*: đợt này đã bổ sung một vấn đề thực có nguồn ngoài (điều khoản nhà cung cấp), một điều kiện cần-và-đủ mới, và ba bộ bằng chứng nhất quán ở ba tầng (vét cạn, mô hình, tiến trình). Điều còn thiếu để một hội đồng A* chấp nhận là bằng chứng trên hợp đồng thật (mục 1–3 ở trên), dữ liệu agent thật (mục 4), và phản biện độc lập về chứng minh, mã và trích dẫn. Quyền chỉ đạo nghiên cứu không thay thế những bước này.
