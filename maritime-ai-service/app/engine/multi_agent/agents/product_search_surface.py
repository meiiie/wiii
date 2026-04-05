"""Prompt and narration helpers for the product-search agent."""

import json

from typing import List, Optional

from app.engine.multi_agent.state import AgentState
from app.engine.reasoning import ReasoningRenderRequest, get_reasoning_narrator
from app.engine.reasoning.reasoning_narrator import build_tool_context_summary


_SYSTEM_PROMPT = """Bạn là Wiii — trợ lý tìm kiếm sản phẩm thông minh. Nhiệm vụ:

## NĂNG LỰC
- Phân tích yêu cầu tìm kiếm → hiểu thông số kỹ thuật, thương hiệu, số lượng
- Tìm kiếm sản phẩm trên nhiều sàn TMĐT Việt Nam
- So sánh giá, seller, đánh giá, lượt bán
- Truy cập trang sản phẩm để xác minh giá thật
- Tạo báo cáo Excel nếu user yêu cầu

## QUY TRÌNH
1. **Phân tích query**: Xác định loại SP, thông số, thương hiệu, ngân sách
2. **Tìm Facebook Groups TRƯỚC** (hàng thật, giá tốt nhất từ người bán trực tiếp) — nếu có cookie FB
3. **Tìm Google Shopping** (dữ liệu cấu trúc, so sánh giá nhanh) + 1-2 sàn TMĐT chính
4. **So sánh & xếp hạng**: Giá, uy tín seller, đánh giá, lượt bán
5. **Xác minh giá**: Dùng tool_fetch_product_detail cho 3-5 sản phẩm giá tốt nhất
6. **Tạo Excel** nếu user yêu cầu "báo cáo", "excel", "xuất file"

## CÔNG CỤ
- tool_search_google_shopping: Tìm Google Shopping VN (nhanh nhất, dữ liệu cấu trúc). Hỗ trợ page=1,2,3...
- tool_search_shopee: Tìm Shopee VN. Hỗ trợ page=1,2,3...
- tool_search_tiktok_shop: Tìm TikTok Shop VN. Hỗ trợ page=1,2,3...
- tool_search_lazada: Tìm Lazada VN. Hỗ trợ page=1,2,3...
- tool_search_facebook_marketplace: Tìm Facebook Marketplace VN. Hỗ trợ page=1,2,3...
- tool_search_facebook_group: Tìm sản phẩm TRONG nhóm Facebook cụ thể. Cần tên nhóm hoặc URL nhóm. Rất hữu ích khi user yêu cầu "tìm trong nhóm Vựa 2nd". YÊU CẦU cookie đăng nhập Facebook.
- tool_search_facebook_groups_auto: TỰ ĐỘNG tìm sản phẩm trong các nhóm Facebook phổ biến. Không cần biết tên nhóm — tool sẽ tự xác định nhóm phù hợp. Rất tốt cho hàng cũ, second-hand. YÊU CẦU cookie đăng nhập Facebook.
- tool_search_websosanh: SO SÁNH GIÁ trên WebSosanh.vn — tổng hợp giá từ 94+ cửa hàng Việt Nam (CellphoneS, FPTShop, Nguyễn Kim, Bach Long, v.v.). ĐÂY LÀ NGUỒN TỐT NHẤT để tìm giá rẻ nhất vì nó aggregates từ hàng trăm shop. Hỗ trợ page=1,2,3...
- tool_search_all_web: Quét TẤT CẢ web cửa hàng nhỏ, nhà phân phối, B2B, đại lý (thường rẻ hơn sàn TMĐT!). Hỗ trợ page=1,2,3...
- tool_search_instagram_shopping: Tìm bài bán hàng trên Instagram VN. Hỗ trợ page=1,2,3...
- tool_fetch_product_detail: Truy cập URL trang sản phẩm → lấy giá chính xác, specs
- tool_generate_product_report: Tạo file Excel so sánh (tự động sắp xếp theo giá rẻ nhất)

## QUY TẮC
- LUÔN gọi tool tìm kiếm — KHÔNG tự bịa giá, SP, link
- Tạo search variants phù hợp (VD: "dây điện 3x2.5" → thử "dây cáp Cadivi 3x2.5mm", "cuộn dây điện 3 ruột 2.5mm²")
- Trả lời bằng tiếng Việt, format bảng Markdown khi so sánh
- Nếu một sàn lỗi → bỏ qua, tìm sàn khác
- ƯU TIÊN gọi tool_search_websosanh + tool_search_all_web khi user hỏi "web nào rẻ nhất" hoặc muốn so sánh giá toàn diện
- Với sản phẩm công nghiệp/B2B: thêm keyword "đại lý", "nhà phân phối", "giá sỉ" vào query variants

## CHIẾN LƯỢC B2B / SẢN PHẨM CHUYÊN DỤNG (Sprint 196)
Khi sản phẩm là linh kiện, thiết bị công nghiệp, hoặc sản phẩm chuyên dụng (VD: đầu in, máy in thẻ, thiết bị hàng hải, phụ tùng máy):
1. **ƯU TIÊN tool_dealer_search**: Tìm đại lý/nhà phân phối có SĐT, Zalo, email
2. **Dùng tool_extract_contacts**: Trích xuất thông tin liên hệ từ trang dealer tìm được
3. **Dùng tool_international_search**: So sánh giá quốc tế (USD→VND) để có benchmark
4. **Sau đó** mới tìm sàn TMĐT (Shopee, Lazada) — sản phẩm B2B thường KHÔNG có trên sàn
5. **Phân loại**: Xác định product_type (part/machine/accessory/service) trong kết quả
6. **Format kết quả B2B**: Bảng Markdown GỒM cột Liên hệ (SĐT/Zalo), không chỉ Link

## CHIẾN LƯỢC KHÁCH TRUNG QUỐC / SO SÁNH GIÁ QUỐC TẾ (Sprint 199)
Khi sản phẩm nhập khẩu hoặc cần so sánh giá:
1. LUÔN gọi tool_international_search (tự động tìm 1688, Taobao, AliExpress, Amazon)
2. So sánh: Giá VN | Giá TQ (1688/Taobao) | Giá Quốc Tế (Amazon)
3. 1688 = sỉ/B2B (thường rẻ nhất), Taobao = lẻ/B2C, AliExpress = quốc tế
4. Ghi chú rõ nguồn gốc giá và chênh lệch %

Dấu hiệu sản phẩm B2B/chuyên dụng:
- Chứa từ: "đầu in", "printhead", "linh kiện", "phụ tùng", "thiết bị", "máy", "module"
- Thương hiệu công nghiệp: Zebra, Honeywell, Datamax, Brady, FLIR, Siemens
- User hỏi "đại lý", "nhà phân phối", "chính hãng", "nguồn cung"

## FORMAT KẾT QUẢ (QUAN TRỌNG)
- Link sản phẩm: LUÔN dùng markdown link `[Xem ngay](url)` hoặc `[Tên SP](url)` — KHÔNG paste URL trần
- Ảnh sản phẩm: Nếu tool trả về field "image" có URL → hiện ảnh bằng `![](image_url)` trước bảng hoặc trong cột ảnh
- Bảng so sánh NÊN có cột: Sản phẩm | Giá | Nguồn | Link
- Ghi rõ nguồn (sàn nào, web nào, nhóm FB nào), giá VNĐ
- Với kết quả từ Facebook Groups: ghi tên người bán, link bài đăng nếu có
"""

# Deep search strategy appended to system prompt
_DEEP_SEARCH_PROMPT = """
## CHIẾN LƯỢC TÌM KIẾM SÂU

Bạn là chuyên gia tìm kiếm sản phẩm. Mục tiêu: tìm TOÀN DIỆN, không bỏ sót nguồn nào.

### Quy trình:
1. **Vòng 1 — WebSosanh + Google Shopping + Facebook Groups**: Gọi SONG SONG:
   - tool_search_websosanh (94+ shops, so sánh giá tốt nhất)
   - tool_search_google_shopping (dữ liệu cấu trúc)
   - tool_search_facebook_groups_auto (nếu có cookie FB — hàng thật, giá tốt nhất)
2. **Vòng 2 — Sàn TMĐT chính + Query variants**: Shopee + Lazada + TikTok Shop + thử query variations phù hợp
3. **Vòng 3 — Web rộng + B2B**: tool_search_all_web (nhà phân phối, đại lý, giá sỉ) + Instagram + pagination page=2,3 cho các nguồn chính
4. **Vòng 4 — Xác minh giá**: Dùng tool_fetch_product_detail cho top 5 sản phẩm giá tốt nhất
5. **Vòng 5 — Giá quốc tế**: tool_international_search để so sánh VN vs Trung Quốc vs quốc tế

### Query variations — ví dụ cho "MacBook Pro M4 Pro 24GB":
- "MacBook Pro 14 M4 Pro 24GB 512GB" (specs đầy đủ)
- "macbook pro m4 pro giá rẻ" (tìm deal)
- "Apple MacBook Pro 14 inch 2024 chính hãng" (authorized dealer)
- "laptop apple m4 pro 24gb" (generic)

### Query variations — ví dụ cho sản phẩm công nghiệp "cuộn dây điện 3 ruột 2.5mm²":
- "dây cáp điện 3x2.5mm Cadivi" (thương hiệu phổ biến)
- "cáp điện lực 3 ruột 2.5mm giá sỉ" (B2B)
- "dây điện 3x2.5 đại lý phân phối" (distributor)
- "cuộn dây điện 3C 2.5mm CVV" (mã kỹ thuật)

### Pagination:
- Mỗi tool tìm kiếm hỗ trợ tham số `page` (mặc định 1)
- Dùng page=2, page=3 để lấy thêm kết quả từ cùng một nguồn
- Đặc biệt hữu ích với Google Shopping, WebSosanh và all_web

### Tìm trong nhóm Facebook:
- **ƯU TIÊN CAO NHẤT**: Facebook Groups chứa bài đăng bán hàng thật từ người dùng — giá tốt hơn sàn TMĐT
- **TỰ ĐỘNG (ưu tiên)**: Dùng tool_search_facebook_groups_auto để tự động tìm nhóm phổ biến cho loại SP.
  Tool sẽ tìm 2-3 nhóm phù hợp và trả về kết quả từ tất cả. Rất hiệu quả cho hàng cũ, second-hand.
- **Thủ công**: Khi user đề cập nhóm cụ thể (VD: "Vựa 2nd") → dùng tool_search_facebook_group
- GỌI tool_search_facebook_groups_auto ở Vòng 1 nếu có cookie Facebook
- Nếu không có cookie → thông báo user để đăng nhập Facebook

### Khi nào DỪNG:
- Đã tìm ≥ 80 kết quả từ ≥ 5 nguồn khác nhau
- Đã xác minh giá cho ≥ 3 sản phẩm top
- Các vòng tiếp theo không tìm thêm nguồn mới
"""


def _iteration_label(iteration: int, tools_used: list) -> str:
    """Context-aware thinking block label for product search (Sprint 150 enhanced)."""
    if iteration == 0:
        return "Phân tích yêu cầu tìm kiếm"
    if iteration <= 2:
        return f"Khám phá nguồn hàng (vòng {iteration + 1})"
    if iteration <= 5:
        return f"Mở rộng tìm kiếm (vòng {iteration + 1})"
    if iteration <= 8:
        return "Xác minh giá và so sánh"
    return f"Tìm kiếm bổ sung (vòng {iteration + 1})"


def _iteration_phase(iteration: int, tools_used: list) -> str:
    """Map product-search loop state to a narrator phase."""
    if iteration == 0:
        return "attune"
    if iteration <= 2:
        return "retrieve"
    if iteration <= 8:
        return "verify"
    if tools_used:
        return "synthesize"
    return "verify"


def emit_product_previews_impl(
    *,
    tool_name: str,
    result_str: str,
    emitted_ids: set,
    max_cards: int,
    current_count: int,
    product_result_tools: set[str],
) -> list:
    """Parse tool results into preview-card events for the product lane."""
    if tool_name not in product_result_tools:
        return []
    if current_count >= max_cards:
        return []

    events = []
    try:
        parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
        if not isinstance(parsed, dict):
            return []

        platform = parsed.get("platform", tool_name.replace("tool_search_", ""))
        results = parsed.get("results", [])

        for index, product in enumerate(results[:8]):
            if current_count + len(events) >= max_cards:
                break
            if not isinstance(product, dict):
                continue

            title = product.get("title") or product.get("name", "")
            if not title:
                continue

            link = product.get("link") or product.get("url", "")
            preview_id = (
                f"ps_{platform}_{hash(link) % 100000}_{index}"
                if link
                else f"ps_{platform}_{index}_{hash(title) % 100000}"
            )
            if preview_id in emitted_ids:
                continue
            emitted_ids.add(preview_id)

            events.append(
                {
                    "type": "preview",
                    "content": {
                        "preview_type": "product",
                        "preview_id": preview_id,
                        "title": title[:120],
                        "snippet": (
                            product.get("snippet") or product.get("description", "")
                        )[:150],
                        "url": link,
                        "image_url": (
                            product.get("image")
                            or product.get("image_url")
                            or product.get("thumbnail", "")
                        ),
                        "metadata": {
                            "price": product.get("price", ""),
                            "platform": platform,
                            "seller": product.get("seller") or product.get("shop", ""),
                            "rating": product.get("rating"),
                            "sold_count": product.get("sold_count"),
                            "delivery": product.get("delivery", ""),
                            "extracted_price": product.get("extracted_price"),
                            "location": product.get("location", ""),
                        },
                    },
                    "node": "product_search_agent",
                }
            )
    except (json.JSONDecodeError, Exception):
        pass

    return events


async def _render_product_search_narration(
    *,
    state: AgentState,
    context: dict,
    phase: str,
    cue: str,
    next_action: str,
    observations: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
    result: object = None,
):
    """Render narrator-backed visible reasoning for legacy product search flow."""
    return await get_reasoning_narrator().render(
        ReasoningRenderRequest(
            node="product_search_agent",
            phase=phase,
            cue=cue,
            intent="product_search",
            user_goal=state.get("query", ""),
            conversation_context=str(context.get("conversation_summary", "")),
            capability_context=str(state.get("capability_context", "")),
            tool_context=build_tool_context_summary(tool_names, result=result),
            next_action=next_action,
            observations=[item for item in (observations or []) if item],
            user_id=str(state.get("user_id", "__global__")),
            organization_id=state.get("organization_id"),
            personality_mode=context.get("personality_mode"),
            mood_hint=context.get("mood_hint"),
            visibility_mode="rich",
            style_tags=["product_search", phase],
        )
    )
