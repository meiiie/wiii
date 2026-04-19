"""Prompt and routing constants for the supervisor shell."""

from __future__ import annotations

ROUTING_PROMPT_TEMPLATE = """Bạn là Supervisor Agent cho hệ thống {domain_name}.

**User Role:** {user_role}

## Phân tích theo bước:
1. Xác định intent: lookup (tra cứu) | learning (dạy/giải thích/quiz) | personal (cá nhân) | social (chào hỏi) | off_topic (không liên quan) | web_search (tìm kiếm web/tin tức/pháp luật) | product_search (tìm/so sánh sản phẩm/giá cả trên sàn TMĐT) | colleague_consult (hỏi Bro/đồng nghiệp về trading/crypto/rủi ro — CHỈ khi user_role=admin)
2. Xác định domain: có THỰC SỰ liên quan {domain_name} hay không? (Lưu ý: "tàu" có thể là tàu hỏa, không phải tàu thủy)
3. Kiểm tra phạm vi kiến thức: câu hỏi có NẰM TRONG phạm vi RAG không? {scope_hint}
4. Chọn agent dựa trên intent + domain + user_role

## Agent Mapping:
- RAG_AGENT: intent=lookup VÀ CÓ domain keyword RÕ RÀNG VÀ nằm trong phạm vi kiến thức RAG. {rag_description}
- TUTOR_AGENT: intent=learning VÀ CÓ domain keyword VÀ nằm trong phạm vi kiến thức. {tutor_description}
- MEMORY_AGENT: intent=personal → lịch sử học, preferences, nhớ thông tin
- CODE_STUDIO_AGENT: intent=code_execution → viết/chạy code, tạo app/widget/mô phỏng, tạo file (HTML/Excel/Word/PDF), chụp trang web, xử lý artifact kỹ thuật
- PRODUCT_SEARCH_AGENT: intent=product_search → tìm kiếm sản phẩm, so sánh giá, mua hàng trên sàn TMĐT (Shopee, Lazada, TikTok Shop, Google Shopping, Facebook Marketplace)
- COLLEAGUE_AGENT: intent=colleague_consult VÀ user_role=admin → hỏi ý kiến Bro về trading, crypto, rủi ro thị trường, liquidation
- DIRECT: intent=social HOẶC intent=off_topic HOẶC intent=web_search → chào hỏi, cảm ơn, tạm biệt, câu NGOÀI chuyên môn, tìm kiếm web/tin tức/pháp luật, và các visual/chart inline để nhìn nhanh khi không cần app hay file. DIRECT KHÔNG tạo file kỹ thuật hoặc app hoàn chỉnh

## Quy tắc QUAN TRỌNG:
- "quiz/giải thích/dạy/ôn bài" + domain keyword → TUTOR_AGENT (NOT RAG_AGENT)
- "tra cứu/cho biết/nội dung/quy định" + domain keyword → RAG_AGENT
- Câu hỏi ngắn < 10 ký tự không có domain keyword → DIRECT
- "tên tôi là/tên mình là/nhớ giúp/bạn có nhớ" → MEMORY_AGENT
- "tìm sản phẩm/mua hàng/so sánh giá/tìm trên shopee/lazada/tiktok shop" → PRODUCT_SEARCH_AGENT (intent=product_search)
- "tìm trên web/mạng/internet", "search", "thông tin mới nhất", "tin tức" → DIRECT (intent=web_search, DIRECT có tool tìm kiếm web)
- "nghị định", "thông tư", "văn bản pháp luật" → DIRECT (intent=web_search, DIRECT có tool_search_legal)
- "tin tức hàng hải", "maritime news", "shipping news" → DIRECT (intent=web_search, DIRECT có tool_search_maritime)
- Câu hỏi KHÔNG liên quan {domain_name} → DIRECT (kể cả khi dài, kể cả khi có từ "tàu" nhưng ngữ cảnh không phải hàng hải)
- Từ "tàu" một mình CHƯA ĐỦ để xác định domain — cần thêm ngữ cảnh hàng hải (COLREGs, hải đồ, thuyền trưởng, v.v.)
- Câu hỏi có domain keyword nhưng RẮNG RỜI nằm NGOÀI phạm vi RAG → DIRECT (ví dụ: "Thủ đô Việt Nam ở đâu?" → geography, not maritime)

## Ví dụ:
- "Điều 15 COLREGs nói gì?" → intent=lookup, agent=RAG_AGENT, confidence=0.95
- "Giải thích Điều 15 COLREGs" → intent=learning, agent=TUTOR_AGENT, confidence=0.95
- "Quiz về SOLAS" → intent=learning, agent=TUTOR_AGENT, confidence=0.90
- "Xin chào" → intent=social, agent=DIRECT, confidence=1.0
- "Tên tôi là Nam" → intent=personal, agent=MEMORY_AGENT, confidence=0.95
- "Mức phạt vượt đèn đỏ?" → intent=lookup, agent=RAG_AGENT, confidence=0.90
- "Dạy tôi về biển báo" → intent=learning, agent=TUTOR_AGENT, confidence=0.90
- "Trên tàu đói quá thì làm gì?" → intent=off_topic, agent=DIRECT, confidence=0.95 (nấu ăn, không phải hàng hải)
- "Nấu cơm trên tàu" → intent=off_topic, agent=DIRECT, confidence=0.90 (ẩm thực, không phải hàng hải)
- "Hôm nay thời tiết thế nào?" → intent=off_topic, agent=DIRECT, confidence=0.95 (không liên quan domain)
- "Python là gì?" → intent=off_topic, agent=DIRECT, confidence=0.95 (lập trình, không phải hàng hải)
- "Tìm trên web luật giao thông mới nhất" → intent=web_search, agent=DIRECT, confidence=0.95 (DIRECT có web search tool)
- "Search thông tin mới nhất về AI" → intent=web_search, agent=DIRECT, confidence=0.90
- "Nghị định 100 về phạt giao thông" → intent=web_search, agent=DIRECT, confidence=0.95 (DIRECT có tool_search_legal)
- "Tin tức hàng hải hôm nay" → intent=web_search, agent=DIRECT, confidence=0.95 (DIRECT có tool_search_maritime)
- "Tàu thủy phải mang bao nhiêu áo phao?" → intent=lookup, agent=RAG_AGENT, confidence=0.95 (hàng hải rõ ràng)
- "Quy tắc nhường đường trên biển" → intent=lookup, agent=RAG_AGENT, confidence=0.95
- "Thời sự hôm nay" → intent=web_search, agent=DIRECT, confidence=0.95
- "Giá vàng hôm nay" → intent=web_search, agent=DIRECT, confidence=0.95
- "Thủ đô Việt Nam ở đâu?" → intent=off_topic, agent=DIRECT, confidence=0.95 (địa lý chung, không phải hàng hải chuyên ngành)
- "Tàu hỏa đi Huế mất mấy tiếng?" → intent=off_topic, agent=DIRECT, confidence=0.95 (tàu hỏa, không phải hàng hải)
- "Cách nấu phở bò ngon" → intent=off_topic, agent=DIRECT, confidence=0.95 (ẩm thực, ngoài chuyên môn)
- "Tìm cuộn dây điện 3 ruột 2.5mm²" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.95
- "So sánh giá máy khoan Bosch trên Shopee và Lazada" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.95
- "Mua ốp lưng iPhone 16 ở đâu rẻ nhất?" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.90
- "Tìm trên shopee áo khoác nam" → intent=product_search, agent=PRODUCT_SEARCH_AGENT, confidence=0.95
- "Hỏi Bro về BTC" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.95 (CHỈ khi user_role=admin)
- "Tình hình liquidation thế nào Bro?" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.95 (CHỈ khi user_role=admin)
- "Bro ơi, thị trường crypto hôm nay sao?" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.95 (CHỈ khi user_role=admin)
- "Bro đánh giá rủi ro thế nào?" → intent=colleague_consult, agent=COLLEAGUE_AGENT, confidence=0.90 (CHỈ khi user_role=admin)
- "Viết code Python tính diện tích tam giác" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Tạo biểu đồ so sánh doanh thu" → intent=off_topic, agent=DIRECT, confidence=0.90
- "Xuất file Excel danh sách" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Tạo báo cáo Word" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.90
- "Chụp trang web https://example.com" → intent=code_execution, agent=CODE_STUDIO_AGENT, confidence=0.95
- "Vẽ chart thống kê" → intent=off_topic, agent=DIRECT, confidence=0.90

**Query:** {query}

**User Context:** {context}"""

COMPACT_ROUTING_PROMPT_TEMPLATE = """Ban la Supervisor Agent cua Wiii.

Nhiem vu: nghe mot turn ngan hoac cau tham do nhanh, roi chon lane xu ly dung nhat.

Chon 1 agent:
- DIRECT: chao hoi, bat nhip, tra loi truc tiep, thac mac ngan, visual/chart inline de nhin nhanh
- CODE_STUDIO_AGENT: user dang goi mot thu co the dung/chay/hien ra duoc theo dang app/widget/mo phong/artifact/file
- RAG_AGENT: tra cuu tri thuc/domain cu the
- TUTOR_AGENT: giai thich/day hoc/quiz
- MEMORY_AGENT: goi lai boi canh ca nhan
- PRODUCT_SEARCH_AGENT: tim/so sanh san pham
- COLLEAGUE_AGENT: hoi Bro, chi khi dung ngu canh admin

Quy tac:
- Vi day la turn ngan, dung nghe nhip cau noi thay vi khop keyword co hoc.
- Neu cau noi dang tham do xem Wiii co the mo phong/dung/hien ra duoc khong theo dang app/widget/mo phong, nghieng ve CODE_STUDIO_AGENT.
- Neu cau noi nghieng ve chart/visual de nhin nhanh, nghieng ve DIRECT de con dung lane visual inline.
- Neu cau noi chi la mot nhip giao tiep hoac cam than, nghieng ve DIRECT.
- Chua du tin hieu domain thi khong ep sang RAG/TUTOR.

Query: {query}
Recent context: {context}
Routing hints: {routing_hints}"""

SYNTHESIS_PROMPT = """Tổng hợp các outputs từ agents thành câu trả lời cuối cùng cho HỌC VIÊN:

Query gốc: {query}

Outputs:
{outputs}

QUY TẮC:
- Trả lời trực tiếp cho học viên, KHÔNG viết ở ngôi thứ nhất về quá trình suy nghĩ
- KHÔNG bao gồm "tôi đang phân tích", "tôi nhận thấy", "tôi đang xem xét"
- KHÔNG bao gồm <thinking> tags hoặc nội dung suy luận nội bộ
 - Giữ tự nhiên, thân thiện — khoảng 500 từ khi cần tổng hợp đầy đủ
- Trả lời bằng tiếng Việt
- KHÔNG bắt đầu bằng "Chào bạn", "Chào" hoặc lời chào nếu đây là cuộc trò chuyện đang diễn ra

Tạo câu trả lời:"""

SYNTHESIS_PROMPT_NATURAL = """Tổng hợp các outputs từ agents thành câu trả lời cuối cùng.

Query gốc: {query}

Outputs:
{outputs}

PHONG CÁCH:
- Trả lời trực tiếp, tự nhiên, viết ở ngôi thứ hai
- Trả lời bằng tiếng Việt, giọng ấm áp thân thiện
- Độ dài tùy theo nội dung — ngắn khi đơn giản, chi tiết khi phức tạp
- Đi thẳng vào nội dung — thể hiện sự hiểu biết qua câu trả lời, không qua lời mở đầu

Tạo câu trả lời:"""

SOCIAL_KEYWORDS = [
    "xin chào", "hello", "chào bạn", "chào",
    "cảm ơn", "thank", "thanks", "tạm biệt", "bye",
    "goodbye", "hẹn gặp lại",
]

PERSONAL_KEYWORDS = [
    "tên tôi", "tên mình", "my name",
    "nhớ giúp", "nhớ cho tôi", "remember",
    "lần trước", "last time", "hôm trước",
    "tôi tên là", "tên mình là", "mình tên là",
    "thông tin của tôi", "thông tin của mình",
    "bạn có nhớ", "bạn nhớ",
    "tuổi tôi", "tuổi mình", "nghề của tôi",
]

FAST_WEB_KEYWORDS = [
    "tim tren web", "tim tren mang", "tim tren internet",
    "search", "tin tuc", "moi nhat", "hom nay",
    "nghi dinh", "thong tu", "van ban phap luat",
    "maritime news", "shipping news",
]

FAST_PRODUCT_KEYWORDS = [
    "shopee", "lazada", "tiktok shop", "facebook marketplace",
    "google shopping", "mua", "tim san pham", "so sanh gia",
    "gia re nhat", "mua o dau",
]

CODE_STUDIO_KEYWORDS = [
    "python", "code", "viet code", "chay code", "chay python",
    "javascript", "js", "typescript", "ts", "html", "css", "react",
    "landing page", "website", "web app", "microsite",
    "bieu do", "chart", "plot", "matplotlib", "pandas", "seaborn",
    "png", "svg", "canvas", "artifact", "sandbox",
    "mo phong", "simulation", "simulate", "simulator",
    "animation", "animate", "animated",
    "interactive diagram", "tuong tac",
]

_NORMALIZED_SOCIAL_PREFIXES = (
    "xin chao",
    "chao",
    "hello",
    "hi",
    "hey",
    "cam on",
    "thanks",
    "thank",
    "thank you",
    "tam biet",
    "bye",
    "goodbye",
    "hen gap lai",
)

_SOCIAL_LAUGH_TOKENS = {
    "he", "hehe", "hehehe", "ha", "haha", "hahaha",
    "hi", "hihi", "hihihi", "hoho", "kk", "kkk",
    "keke", "alo", "alooo",
}

_REACTION_TOKENS = {
    "wow", "woah", "whoa", "oa", "oaa", "oi", "oii", "ui",
    "uii", "uay", "uayy", "ah", "a", "oh", "hmm", "hm",
    "uh", "umm", "um", "uhm",
}

_VAGUE_BANTER_PHRASES = {
    "gi do",
    "cai gi do",
    "gi ay",
    "cai gi ay",
}

_IDENTITY_PROBE_MARKERS = (
    "ban la ai",
    "ban ten gi",
    "ten gi",
    "ten cua ban",
    "wiii la ai",
    "wiii ten gi",
    "cuoc song the nao",
    "cuoc song cua ban",
    "song the nao",
    "gioi thieu ve ban",
)

_FAST_CHATTER_BLOCKERS = (
    "tai sao", "la gi", "the nao", "giai thich", "huong dan", "tra cuu",
    "quy dinh", "tin tuc", "search", "tim", "mo phong", "simulation",
    "canvas", "chart", "code", "python", "javascript", "html", "css",
    "react", "excel", "word", "pdf", "bao nhieu", "o dau", "nhu nao",
)

_ROUTING_ARTIFACT_MARKERS = (
    "```", "<!doctype", "<html", "<body", "<div", "<svg",
    "function ", "const ", "let ", "class ", "import ", "export ",
    "visual_session_id", '"type": "visual"',
)

_SUPERVISOR_HEARTBEAT_INTERVAL_SEC = 6.0
CONFIDENCE_THRESHOLD = 0.7
_COMPLEX_QUERY_MIN_LENGTH = 80
_MIXED_INTENT_PAIRS = [
    ("tra cứu", "giải thích"),
    ("nội dung", "dạy"),
    ("quy định", "giải thích"),
    ("luật", "quiz"),
    ("cho biết", "hướng dẫn"),
    ("thông tin", "phân tích"),
]
