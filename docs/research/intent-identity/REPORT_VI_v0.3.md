# Báo cáo nghiên cứu v0.3

**Exactly-Once Effects for Regrouping Agent Tool Calls: A Reduction, a Retention Hazard, and an Evidence Contract**
(tên cũ: *Intent Identity and Exactly-Once Effects for Non-Deterministic LLM Agents*)

Ngày: 19 tháng 9 năm 2026. Trạng thái: kết quả phát triển đã chạy; cài đặt thứ hai viết từ đặc tả v0.2 bởi cùng quy trình nghiên cứu (không phải tái lập bên ngoài); đã qua hai vòng phản biện đối kháng nội bộ và sửa; chưa nộp.

## 1. Quyết định điều hành sau đợt v0.3

Đợt v0.2 kết thúc với một kết quả âm: đối chứng mạnh dùng khóa ổn định theo nghĩa vụ hòa với bộ xác minh trong mọi miền đã thử. Báo cáo v0.2 mục 7 đặt điều kiện tiếp theo: *tìm được một vấn đề thực mà đối chứng tốt chưa giải quyết*. Đợt này đã tìm được vấn đề đó, và nó không phải là một giả thiết do ta dựng lên mà là **điều khoản hợp đồng đã được nhà cung cấp công bố**:

- Stripe xóa khóa idempotency sau ít nhất 24 giờ và "tạo yêu cầu mới nếu khóa được dùng lại sau khi bản gốc đã bị xóa".
- Amazon SQS FIFO chỉ chống lặp trong cửa sổ 5 phút.

Giả thiết nền của phép quy giản trong v0.2 ("sink giữ khóa trong toàn bộ quá trình khôi phục") vì thế **không phải điều nhà cung cấp cam kết**. Khi khôi phục diễn ra sau cửa sổ (mất điện dài, khôi phục checkpoint muộn), mọi chính sách retry-cùng-khóa, kể cả đối chứng mạnh và bộ xác minh v0.2, đều tạo hiệu ứng lặp. Đây là kết quả trung tâm của v0.3 và đã được chứng minh, vét cạn, kiểm tra mô hình và chạy tiến trình thật.

Quyết định: giữ nguyên kết quả âm v0.2 ở vị trí trung tâm (nay được tái lập bởi một cài đặt thứ hai), viết lại đóng góp quanh **ranh giới của phép quy giản** và **hai hợp đồng nằm ngoài ranh giới đó** (cửa sổ giữ khóa và bằng chứng kết quả). Chưa nộp. Chưa gọi model. Chưa gọi API thương mại.

## 2. Đã làm gì trong đợt này

### 2.1. Tái lập toàn bộ v0.2 bằng một cài đặt thứ hai

Mã nguồn v0.2 không có trong phiên này; artifact v0.3 được viết mới hoàn toàn từ đặc tả trong bản thảo v0.2 (Python thư viện chuẩn + SQLite). Điều này làm giảm mối đe dọa "cùng mã" mà v0.2 nêu ở mục IX.B nhưng **không** loại bỏ mối đe dọa "cùng nhóm": cùng một quy trình nghiên cứu viết cả hai bản, nên đây không phải tái lập độc lập bên ngoài. Bài báo nói rõ điều này.

| Hạng mục | v0.2 | v0.3 (cài đặt thứ hai) | Khớp |
| --- | --- | --- | --- |
| D1 số trường hợp | 186.674 | 186.674 | có |
| D1 lặp của khóa theo nhóm (G) | 130.348 (16 / 1.308 / 129.024) | 130.348 (16 / 1.308 / 129.024) | chính xác |
| D1 R và V | 0 lặp, 0 sai khác | 0 lặp, 0 sai khác | có |
| E1 | 65.535 tập; 1.048.560 phép kiểm; 941 tập có frontier khác rỗng | giống hệt | chính xác |
| E3 | công thức khớp oracle đến n = 8 | khớp đến n = 10 (mở rộng) | có |
| I1 | 240/240 | 240/240 | có |
| I2 | 24/24 | 24/24 | có |
| M1 | 480 trạng thái / 1.266 chuyển | 1.180 / 3.467 (mã hóa khác) | cùng dạng phản ví dụ; số không so sánh được |

Điểm bổ sung quan trọng: đối chứng được **làm mạnh thêm** thành `R+` (tham chiếu sổ cái của chính nó trước khi gửi). `R+` hòa `V` cả về vector hiệu ứng lẫn số lời gọi sink (372.145 so với 744.290 của `R` cũ). Vòng phản biện chỉ ra rằng kết quả hòa này là **cấu trúc, không phải thực nghiệm**: cả hai chính sách đều tính "đã duyệt và chưa xong" cho từng nghĩa vụ rồi gửi cùng khóa cùng byte, nên bằng nhau theo một bổ đề một dòng (Bổ đề 1 trong bài). Bảng D1 vì thế là phép kiểm tra cài đặt, không phải bằng chứng cho một giả thuyết. Kết quả âm v0.2 vẫn đứng và còn sắc hơn: bộ xác minh không tiết kiệm được gì so với một đối chứng chịu đọc sổ cái của mình.

Số 1.061 − 1.056 = 5 lời gọi dư trong v0.2 mà đánh giá trước đã hỏi: trong v0.3, số lời gọi dư đúng bằng số lượt retry sau mất xác nhận (120 = 60 + 60 lượt ở hai điểm lỗi "sau hiệu ứng, trước xác nhận"), tất cả được provider trả lời bằng receipt đã lưu. Con số 5 của v0.2 chưa giải thích được từ đặc tả và cần đối chiếu với mã gốc.

### 2.2. Kết quả mới: cửa sổ giữ khóa hữu hạn

**Định nghĩa.** Profile `P_D(T)`: sink chống lặp theo khóa trong ít nhất `T` kể từ lần commit đầu; sau đó khóa có thể bị xóa và yêu cầu cùng khóa có thể commit lần nữa. Stripe là `P_D(T ≥ 24h)`; SQS FIFO là `P_D(T = 5 phút)`.

**Mệnh đề 3 (retry cùng khóa dưới cửa sổ hữu hạn).** Controller ghi bền thời điểm giữ `h(ω)` trước khi truyền và retry cùng khóa tại thời điểm `t`. Gọi `Δ` là chặn trên của **sai số thời gian đầu-cuối** giữa khoảng cách hai lần gửi đo ở controller và khoảng cách hai lần đến đo ở sink (bao gồm trễ giao hàng và, nếu đồng hồ có thể nhảy giữa hai lần, hai lần chặn lệch đồng hồ). Với mô hình đối kháng tường minh trong đó kẻ thù chọn sai số bất kỳ trong `[−Δ, Δ]` cùng với mọi lịch sử mất-xác-nhận, retry an toàn trong mọi lịch sử chấp nhận được **khi và chỉ khi** `t − h(ω) < T − Δ`, với thêm giả thiết thời gian sống của một attempt `L` thỏa `L + Δ < T` (attempt hoặc commit trong khoảng đó hoặc không bao giờ). Nếu attempt có thể sống lâu hơn cửa sổ thì không có thời điểm retry nào an toàn: yêu cầu gốc đến sau khi bản ghi của retry đã hết hạn. Đây là lỗ trong phát biểu vòng trước, cùng dạng với trường hợp I3 "sớm". Phiên bản v0.3 đầu tiên phát biểu điều này với một `δ` mơ hồ; vòng phản biện yêu cầu và đã nhận được mô hình thời gian tường minh. Quyết định chỉ cần sổ cái của controller và hai tham số hợp đồng `T`, `Δ`; **không truy vấn sink nào thay thế được nó**, vì tra cứu âm sau khi khóa bị xóa phù hợp với cả hai lịch sử. Các thí nghiệm chạy với `Δ = 0` trên một máy, tức chỉ kiểm cửa sổ, chưa kiểm biên an toàn.

**Hệ quả.** Sau cửa sổ, `P_D(T)` xuống cấp thành `P_F` (nếu có fence hoặc bằng chứng) hoặc `P_O`. Controller nhận biết cửa sổ = controller khóa ổn định + bước xuống cấp này: bằng chứng dương thì xác nhận; có fence thì cấp khóa mới; không có gì thì chuyển sang trạng thái `unresolved` (an toàn, chưa hoàn thành).

**Bằng chứng đã chạy:**

| Nghiên cứu | Kết quả |
| --- | --- |
| D1-TTL (186.674 trường hợp × 3 trạng thái tại lúc crash) | Khi index chống lặp đã bị xóa và xác nhận bị mất: `R`, `R+`, `V` lặp trong **toàn bộ 149.217** trường hợp có tiền tố đã commit. Chính sách nhận biết cửa sổ `Vr`: 0 lặp, 149.217 `unresolved`. `Vr+E` (có tra cứu): 0 lặp, hoàn thành đủ khi xác nhận bị mất; nhưng khi nghĩa vụ chỉ mới được giữ chỗ chưa có hiệu ứng, tra cứu âm **không phải bằng chứng kết cục** nên `Vr+E` cũng dừng ở `unresolved` (149.217) và tốn thêm một lời gọi. Bản v0.3 đầu tiên đã mô hình sai chỗ này (coi tra cứu âm là đủ để gửi lại); vòng phản biện phát hiện và đã sửa cho khớp với runtime I4. Các số này là hệ quả của Mệnh đề 3 áp cho từng trường hợp, có vai trò kiểm tra cài đặt. |
| M1, mutant mới "retry sau khi hết cửa sổ" | Phản ví dụ 7 bước: hold, send, commit, crash, hết cửa sổ, resend cùng khóa, commit. Cấu hình an toàn có thêm chuyển trạng thái hết cửa sổ vẫn duyệt hết 1.396 trạng thái không vi phạm. Cấu hình mới "an toàn, sink không có fence" cũng duyệt hết (76 trạng thái) vì sau cửa sổ controller chỉ còn cách dừng; M1 chỉ kiểm an toàn, **không kiểm liveness**, và đây đúng là cấu hình controller có thể an toàn bằng cách không bao giờ hoàn thành. |
| I4 (80 lượt tiến trình thật, provider có TTL 0,5 s, khôi phục sau 0,8 s) | Retry ngây thơ sau mất xác nhận: lặp **20/20** (cả R và V). Khôi phục nhận biết cửa sổ: lặp 0/40; có endpoint tra cứu thì hoàn thành 10/10; không có thì `unresolved` 10/10. |

### 2.3. Kết quả mới: tiếp quản khi yêu cầu cũ còn đang bay (I3)

Đánh giá v0.2 chỉ ra I2 (ba worker đua) không bao giờ chạm tới cơ chế chống lặp của provider vì reservation ở controller đã phân xử. Đo lại trong v0.3: **0/96** lời gọi sink trong I2 là dedup. Vì thế thiết kế thêm I3: worker A bị SIGKILL 150 ms sau khi gửi trong khi provider cố tình trễ commit; worker B tiếp quản slot đang `held` sau khi lease hết. Vòng phản biện chỉ ra đối chứng "ngây thơ" (retry cùng khóa bất kể profile) là đúng theo định nghĩa, nên đã bổ sung đối chứng **thực tế**: *tra cứu rồi cấp khóa mới, không fence* (`lookup-fresh`). Đây là handler viết tay. Engine kiểu durable-execution mà khóa retry là định danh activity thì chính là hàng "ngây thơ" (cùng khóa), và nó hỏng khi cửa sổ đã đóng (I4), không phải khi yêu cầu còn đang bay. Tổng cộng 3 profile × 2 thời điểm × 3 chính sách × 5 = 90 lượt.

| Profile | Khôi phục | Lặp (trên 5) | Cơ chế |
| --- | --- | --- | --- |
| P_D | ngây thơ / nhận biết | 0 / 0 | dedup của sink (yêu cầu cũ tới sau → receipt) |
| P_D | tra cứu → khóa mới, **sớm** | **5** | không có: hai khóa khác nhau → hai hiệu ứng; dedup theo khóa không giúp được |
| P_D | tra cứu → khóa mới, muộn | 0 | tra cứu dương → xác nhận |
| P_F | ngây thơ | 5 | không có |
| P_F | tra cứu → khóa mới, sớm / muộn | 5 / 0 | không có / tra cứu dương |
| P_F | nhận biết | 0 | fence chặn yêu cầu cũ → khóa mới; hoặc fence trả receipt |
| P_O | ngây thơ | 5 | không có |
| P_O | tra cứu → khóa mới, sớm / muộn | 5 / 0 | không có / tra cứu dương |
| P_O | nhận biết, sớm | 0 (5 `unresolved`) | dừng lại; 0,5 s sau thế giới đã hoàn thành mà controller không biết |
| P_O | nhận biết, muộn | 0 | tra cứu dương → xác nhận |

Ba cơ chế cần thiết (dedup của sink, fence-rồi-khóa-mới, trạng thái `unresolved` tường minh) xuất hiện thành ba dòng đo được, thay vì chỉ là văn xuôi. Phát hiện đáng chú ý nhất của vòng này: đối chứng thực tế `lookup-fresh` **lặp 15/15 khi yêu cầu cũ còn đang bay, trên mọi profile kể cả `P_D`**, và đúng 15/15 khi yêu cầu cũ đã hạ. Đây là trường hợp một handler khôi phục viết cẩn thận vẫn rơi vào: tra cứu âm tại một thời điểm không phải bằng chứng kết cục, và fence là phép toán duy nhất trong mô hình biến nó thành kết cục. Đây cũng là bản chạy thật của witness 9 bước "absence without fence" trong M1.

### 2.4. Kết quả mới: predecessor bị treo rồi tiếp tục (I6)

Phản biện hỏi: điều gì xảy ra nếu worker cũ **không chết** mà chỉ bị treo (scheduler, debugger, di trú VM, GC pause dài) rồi tiếp tục với lease đã mất? I6 trả lời bằng tiến trình thật: worker A bị SIGSTOP (sau khi giữ chỗ o1, hoặc 150 ms sau khi gửi trong khi provider trễ commit 1 s); worker B tiếp quản ở 0,5 s với chính sách nhận biết; A được SIGCONT ở 1,6 s và chạy đến hết. 3 profile × 2 điểm treo × 2 quy tắc sổ cái × 5 = 60 lượt.

| Profile | Yêu cầu muộn của A | Ghi sổ của A | Lặp | Kết quả |
| --- | --- | --- | --- | --- |
| P_D | dedup của sink trả receipt | bị từ chối (không giữ lease), 5/5 | 0 | B đã xong; A đọc `done` của B cho o2–o4 |
| P_F | fence của B chặn ở provider, 5/5 | không có gì để ghi | 0 | B đã cấp khóa mới và xong |
| P_O, quy tắc nghiêm | commit (không gì chặn) | receipt bị từ chối, 5/5 | 0 | controller kẹt `unresolved` dù thế giới đã đủ |
| P_O, quy tắc nhận bằng chứng muộn | commit | receipt được **nhận**, 5/5 | 0 | hoàn thành 5/5 |

Ba nhận xét. (1) Quy tắc lease-holder của sổ cái làm đúng việc của nó: mọi ghi trạng thái của zombie bị từ chối và ghi thành sự kiện; zombie hoàn thành phần còn lại bằng cách đọc bản ghi `done` của B, không thực thi lại. (2) Không lặp **không phải nhờ** quy tắc đó: dưới P_D là dedup của sink, dưới P_F là fence của B, dưới P_O là vì B đã đúng khi không cấp khóa mới. Zombie chỉ là một yêu cầu đang bay đến rất muộn; cơ chế của bảng I3 chi phối nó. (3) Dưới P_O, zombie mang **bằng chứng kết cục duy nhất tồn tại**: một receipt gắn đúng khóa và hash payload của nghĩa vụ mà B phải bỏ `unresolved`. Sổ cái coi mọi ghi từ người không giữ lease là "tuyên bố cũ" sẽ vứt bỏ bằng chứng đó và kẹt ở chưa hoàn thành. Tách hai câu hỏi — *ai được chuyển trạng thái* (người giữ lease) và *cái gì được tính là bằng chứng* (receipt có ràng buộc khớp) — cho phép nghĩa vụ `unresolved` nhận receipt muộn, trong khi `held` và `done` vẫn từ chối. An toàn vì `unresolved` theo định nghĩa không có khóa mới đang bay và không có bằng chứng khác; bị từ chối tự động nếu B đã đổi khóa (ràng buộc không khớp). Quy tắc này được thiết kế **sau khi** quan sát kết quả của quy tắc nghiêm và được báo cáo như hệ quả thiết kế kèm đo lường riêng, không phải giả thuyết đặt trước.

### 2.5. Kết quả mới: lớp ngữ nghĩa batch quyết định tập niềm tin (E4)

Nguồn của "tương quan" trong v0.2 mục V hóa ra không hề lạ: đó là **cách provider xử lý một yêu cầu batch** mà phản hồi đã mất. Nếu journal ghi thành viên, thứ tự và lớp xử lý của yêu cầu, tập niềm tin được xác định hoàn toàn:

| Lớp | Tập đã hoàn thành khả dĩ | Kỳ vọng số truy vấn tối ưu | Journal ba trạng thái |
| --- | --- | --- | --- |
| độc lập (SQS batch, SES bulk) | mọi tập con | n | n |
| nguyên tử (một yêu cầu Stripe) | ∅ hoặc tất cả | 1 | n |
| tiền tố (xử lý tuần tự, dừng khi lỗi) | các tiền tố | ⌈log₂(n+1)⌉ − (2^⌈log₂(n+1)⌉ − (n+1))/(n+1); n = 8 → 3,22 | n |
| đúng k (tổng hợp đáng tin) | các k-tập | công thức v0.2; n = 8, k = 4 → 6,4 probe **cộng một lời gọi tổng hợp** để biết k | n |

Oracle động quy hoạch chính xác khớp mọi công thức đóng đến n = 10. Chi phí giữ thông tin này: một trường mỗi yêu cầu. Vòng phản biện đòi hỏi hai điểm: (a) lớp đúng-k **không** được xác định từ journal (cần một lời gọi tổng hợp sau đó), nên mệnh đề đủ-journal chỉ còn ba lớp độc lập/nguyên tử/tiền tố; (b) chi phí phải được tính dưới **hai cách kế toán**: *kết cục theo yêu cầu* (chỉ tính probe) và *kết cục theo khóa* (mọi entry vắng mặt phải được fence trước khi gửi lại). Dưới cách kế toán thứ hai, probe một entry vắng mặt chính là fence mà entry đó cần, nên nó không tốn thêm; chính sách tối thiểu số probe vì thế không còn tối ưu. Quét từ cuối yêu cầu rồi dừng ở entry đã commit đầu tiên tốn `n/2 + n/(n+1)`: n = 8 → 4,5 (nguyên tử) và 4,89 (tiền tố) thay vì 8, và thay vì 5,78 của chính sách cũ. Xấu nhất vẫn là n khi không gì đã commit.

**Đã kiểm chứng trên runtime (I5, 141 lượt):** worker gửi một yêu cầu batch rồi bị SIGKILL trước khi đọc phản hồi; provider làm lỗi các entry theo "thế giới" được chọn; mọi thế giới của mỗi lớp đều được chạy một lần dưới mỗi cách kế toán (68 × 2), cộng 5 thế giới tiền tố với journal **khai sai lớp** là nguyên tử. Successor khôi phục từ journal ba trạng thái hoặc journal có cấu trúc:

| Lớp / n | Ba trạng thái (probe TB) | Có cấu trúc (probe TB) | Oracle | Có cấu trúc + fence (lời gọi TB) | Oracle E4 |
| --- | --- | --- | --- | --- | --- |
| độc lập / 4 | 4,00 | 4,00 | 4,00 | 4,00 | 4,00 |
| nguyên tử / 4 | 4,00 | 1,00 | 1,00 | 2,50 | 2,50 |
| tiền tố / 4 | 4,00 | 2,40 | 2,40 | 2,80 | 2,80 |
| tiền tố / 8 | 8,00 | 3,22 | 3,22 | 4,89 | 4,89 |
| nguyên tử / 8 | 8,00 | 1,00 | 1,00 | 4,50 | 4,50 |

Toàn bộ 136 lượt đúng lớp đều exactly-once và hoàn thành đủ (entry vắng mặt được gửi lại bằng khóa mới sau khi đã xác định thế giới). Số probe và số lời gọi đo được trùng khớp kỳ vọng của oracle ở mọi ô, dưới cả hai cách kế toán. **Khai sai lớp** (provider xử lý tiền tố, journal nói nguyên tử): controller probe một entry, suy ra phần còn lại, báo hoàn thành cả 5/5 lượt; trong 3/5 thế giới, bảng hiệu ứng của provider cho thấy các nghĩa vụ còn lại chưa từng xảy ra (**hoàn thành giả**), không có lặp. Lớp xử lý và `T` là dữ liệu hợp đồng được tin cậy; khai sai theo chiều ngược lại (độc lập khai là tiền tố) sẽ cho lỗi ngược: gửi lại một entry đã commit. Kết luận vẫn giữ đúng phạm vi: thông tin bị bỏ đi bởi phép chiếu ba trạng thái, không phải mọi journal ba trạng thái đều không thể mở rộng.

## 3. Đóng góp được viết lại như thế nào

Không được viết: "Bộ xác minh của chúng tôi vượt idempotency." Câu đúng bây giờ:

1. Khóa nghĩa vụ ổn định là đủ cho exactly-once của agent đổi kế hoạch **đúng chừng nào sink còn giữ khóa**; cài đặt thứ hai xác nhận bộ xác minh không thêm gì dưới giả thiết đó.
2. Sink thương mại **giới hạn** thời gian giữ khóa. Ngoài giới hạn, cùng những chính sách ấy lặp trong mọi trường hợp mất xác nhận. Retry cùng khóa an toàn khi và chỉ khi `t − h(ω) < T − Δ` và mọi attempt commit hoặc chết trong thời gian sống `L` với `L + Δ < T`. Nếu attempt sống lâu hơn cửa sổ thì không có thời điểm retry nào an toàn.
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
- I3/I4 dựa trên sleep; xác định trong môi trường này với 5 lần lặp mỗi ô; là minh chứng cơ chế, không phải đo tần suất. Kết cục của yêu cầu bị mất trong I5 do lịch chạy cung cấp (successor khởi động sau khi provider xong); dưới cách kế toán theo khóa thì fence cung cấp thay; hai cách kế toán kẹp lấy điều một provider thật sẽ cung cấp.
- Nhiều kết quả đúng theo cấu trúc và được báo cáo như phép kiểm tra, không phải phát hiện: đối chứng ngây thơ lặp sau cửa sổ vì nó được định nghĩa là retry cùng khóa; các số D1-TTL là hệ quả của Mệnh đề 3; `R+` hòa `V` theo Bổ đề 1.
- I6 thử predecessor bị treo rồi tiếp tục ở mức tiến trình, nhưng với một cú treo *hợp tác*: zombie chỉ được đánh thức sau khi successor đã xong. Zombie tỉnh lại *trong lúc* successor đang khôi phục sẽ đua với fence/đổi khóa ở sổ cái; quy tắc lease-holder tuần tự hóa phía sổ cái trong một giao dịch SQLite, nhưng phía provider lại là trường hợp I3 "sớm" và dựa vào fence hoặc dedup, không dựa vào sổ cái.
- Số trạng thái M1 khác v0.2 vì mã hóa khác; chỉ dạng phản ví dụ là so sánh được.
- Đặc tả các preprint arXiv 2026 (ACRFence, CapLease, AID-Guard, Cordon, PCA) được kế thừa từ audit tài liệu v0.2 và **phải được người kiểm tra lại** trước khi nộp.
- Đối chứng và bộ xác minh dùng chung tầng lưu trữ/truyền tải trong runtime; nghiên cứu vét cạn trừu tượng tồn tại song song vì lý do này.

## 6. Gói bàn giao

- `paper/main.tex`, `paper/main.pdf`: bản thảo v0.3, IEEEtran, 12 trang, 8 bảng, 1 hình TikZ, 6 mệnh đề, 36 tài liệu tham khảo. Trong đó có 6 nguồn tài liệu nhà cung cấp (có URL và ngày truy cập) và dòng at-most-once / exactly-once mà vòng phản biện thứ hai yêu cầu: Liskov–Shrira–Wroclawski, Birrell–Nelson, Lampson, leases, Chubby, Olive, Beldi, Boki, Durable Functions.
- `artifact/`: mã (9 module), 37 kiểm thử kernel, 5 driver thí nghiệm, `run_all.py` tái lập toàn bộ (~15 phút trên một lõi), kết quả thô: 635 lượt tiến trình với mã trả về, marker crash, tóm tắt successor và số đếm phía provider; các phép liệt kê vét cạn; witness của bộ duyệt mô hình.
- `PROVIDER_CONTRACTS.md`: trích dẫn nguyên văn có ngày.
- `EVIDENCE_SUMMARY_v0.3.json`: mọi con số trong bài dưới dạng máy đọc.

Không có model weights, API key, chi phí inference, thay đổi sản xuất hay bài nộp nào.

## 7. Cổng đánh giá tiếp theo

1. **Xác thực cửa sổ với tài khoản sandbox** của một provider `P_D(T)` (Stripe test mode): tạo object với khóa, chờ quá cửa sổ, dùng lại khóa, đọc kết quả. Không tốn tiền hiệu ứng thật. Đây là bước biến "điều khoản đã công bố" thành "hành vi đã quan sát".
2. **Ba adapter, ba profile**: kiểm tra bộ trường hợp đồng (`T`, evidence, batch_class) đủ để controller chọn đúng nhánh khôi phục cho Stripe (`P_D(T)` + lookup), SQS FIFO (`P_D(T)` không lookup), Slack (`P_O` + history có rate limit).
3. **Một provider có lớp batch khác "độc lập"** để kiểm chứng giá trị của journal có cấu trúc trên hợp đồng thật.
4. **Thu thập đề xuất LLM tự nhiên** tách khỏi biến đổi cưỡng bức; giữ prompt, phiên bản model, cấu hình sinh và toàn bộ output lỗi.
5. Nếu cả (1) và (3) đạt: bộ trường hợp đồng runtime trở thành sản phẩm bàn giao. Nếu không: giữ là nghiên cứu tái lập / kết quả âm kèm một mối nguy đã được ghi nhận.

Về mục tiêu A*: đợt này đã bổ sung một vấn đề thực có nguồn ngoài (điều khoản nhà cung cấp), một điều kiện cần-và-đủ với mô hình thời gian tường minh, một đối chứng thực tế bị đánh bại đúng chỗ (tra cứu → khóa mới lặp 15/15 khi yêu cầu cũ còn bay), và ba bộ bằng chứng nhất quán ở ba tầng (vét cạn, mô hình, tiến trình) dưới hai cách kế toán chi phí. Hai vòng phản biện đối kháng nội bộ đã tìm ra và sửa: mô hình `Vr+E` sai, Mệnh đề 3 chưa chặn attempt gốc đến muộn, lớp đúng-k không đủ-journal, chính sách tối thiểu probe không tối ưu khi mỗi probe là một fence, `rekey` không mở cửa sổ giữ mới, sổ cái không kiểm lease-holder, và các phát biểu "độc lập" quá tay. Điều còn thiếu để một hội đồng A* chấp nhận là bằng chứng trên hợp đồng thật (mục 1–3 ở trên), dữ liệu agent thật (mục 4), và phản biện độc lập bên ngoài về chứng minh, mã và trích dẫn. Quyền chỉ đạo nghiên cứu không thay thế những bước này.
