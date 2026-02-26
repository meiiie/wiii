"""
Product Search Agent Node — Sprint 148→150→200: "Săn Hàng" → "Tìm Sâu" → "Mắt Sản Phẩm"

Specialized LangGraph node for multi-platform e-commerce product search.
Uses ReAct loop (LLM→tools→observe→decide) pattern from tutor_node.py.

Sprint 150 enhancements:
- Configurable max iterations (default 15, was hardcoded 5)
- Enhanced deep search system prompt with multi-round strategy
- Context-aware iteration labels
- Page scraper tool integration (tool_fetch_product_detail)
- Pagination support (page parameter on all search tools)

Sprint 200 enhancements:
- Real-time preview card emission during ReAct loop (product carousel)
- Visual product search (image → product identification via Gemini Vision)
- Image pass-through from AgentState for visual search routing
"""

import asyncio
import json
import logging
import threading
from typing import Dict, List, Optional, Tuple

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)

# Max ReAct iterations — read from config at runtime, fallback to default
_MAX_ITERATIONS_DEFAULT = 15

# Chunk streaming config (matches tutor_node.py)
_CHUNK_SIZE = 40
_CHUNK_DELAY = 0.008  # 8ms

# Post-tool acknowledgment templates
_TOOL_ACK = {
    "tool_search_google_shopping": "Tìm được từ Google Shopping! Đang phân tích...",
    "tool_search_shopee": "Đã tìm trên Shopee! Đang xem kết quả...",
    "tool_search_tiktok_shop": "Đã tìm trên TikTok Shop! Đang so sánh...",
    "tool_search_lazada": "Đã tìm trên Lazada! Đang tổng hợp...",
    "tool_search_facebook_marketplace": "Đã tìm trên Facebook Marketplace!",
    "tool_search_facebook_search": "Đã tìm trên Facebook! Đang phân tích kết quả...",
    "tool_search_facebook_group": "Đã tìm trong nhóm Facebook! Đang phân tích bài đăng...",
    "tool_search_facebook_groups_auto": "Đang quét các nhóm Facebook phổ biến — nguồn hàng tốt nhất!",
    "tool_search_all_web": "Đã quét web cửa hàng nhỏ! Đang xem giá...",
    "tool_search_websosanh": "Đang so sánh giá trên 94+ cửa hàng Việt Nam qua WebSosanh!",
    "tool_search_instagram_shopping": "Đã tìm trên Instagram!",
    "tool_generate_product_report": "Báo cáo Excel đã được tạo!",
    "tool_fetch_product_detail": "Đã truy cập trang sản phẩm! Đang đọc giá...",
    # Sprint 196: B2B sourcing tool acknowledgments
    "tool_dealer_search": "Đang tìm đại lý và nhà phân phối! Trích xuất thông tin liên hệ...",
    "tool_extract_contacts": "Đang trích xuất SĐT, Zalo, email từ trang web...",
    "tool_international_search": "Đang tìm giá quốc tế (1688, Taobao, AliExpress, Amazon)! Chuyển đổi sang VNĐ...",
    # Sprint 200: Visual product search
    "tool_identify_product_from_image": "Đang nhận diện sản phẩm từ ảnh bằng AI Vision...",
}

# Sprint 200: Tool names that produce product search results
_PRODUCT_RESULT_TOOLS = {
    "tool_search_google_shopping", "tool_search_shopee", "tool_search_tiktok_shop",
    "tool_search_lazada", "tool_search_facebook_marketplace", "tool_search_all_web",
    "tool_search_instagram_shopping", "tool_search_websosanh",
    "tool_search_facebook_search", "tool_search_facebook_group",
    "tool_search_facebook_groups_auto",
    "tool_international_search", "tool_dealer_search",
}


def _emit_product_previews(
    tool_name: str,
    result_str: str,
    emitted_ids: set,
    max_cards: int,
    current_count: int,
) -> list:
    """Parse tool results and generate preview event dicts for product cards.

    Returns list of preview event dicts to push to event_queue.
    Non-critical — returns empty list on any error.
    """
    if tool_name not in _PRODUCT_RESULT_TOOLS:
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

        for i, product in enumerate(results[:8]):
            if current_count + len(events) >= max_cards:
                break
            if not isinstance(product, dict):
                continue
            title = product.get("title") or product.get("name", "")
            if not title:
                continue

            # Dedup by product URL
            link = product.get("link") or product.get("url", "")
            pid = f"ps_{platform}_{hash(link) % 100000}_{i}" if link else f"ps_{platform}_{i}_{hash(title) % 100000}"
            if pid in emitted_ids:
                continue
            emitted_ids.add(pid)

            events.append({
                "type": "preview",
                "content": {
                    "preview_type": "product",
                    "preview_id": pid,
                    "title": title[:120],
                    "snippet": (product.get("snippet") or product.get("description", ""))[:150],
                    "url": link,
                    "image_url": product.get("image") or product.get("image_url") or product.get("thumbnail", ""),
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
            })
    except (json.JSONDecodeError, Exception):
        pass

    return events


# Vietnamese system prompt for product search agent
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


class ProductSearchAgentNode:
    """Agent node for multi-platform product search via ReAct loop."""

    def __init__(self):
        self._llm = None
        self._llm_with_tools = None
        self._tools = []
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM and bind product search tools."""
        try:
            from app.engine.multi_agent.agent_config import AgentConfigRegistry
            self._llm = AgentConfigRegistry.get_llm("product_search")
            if not self._llm:
                # Fallback to direct node config
                self._llm = AgentConfigRegistry.get_llm("direct")
        except Exception as e:
            logger.warning("[PRODUCT_SEARCH] LLM init failed: %s", e)

        # Load tools
        try:
            from app.engine.tools.product_search_tools import get_product_search_tools
            from app.engine.tools.excel_report_tool import tool_generate_product_report
            self._tools = get_product_search_tools() + [tool_generate_product_report]
            # Sprint 150: Add page scraper tool
            try:
                from app.engine.tools.product_page_scraper import tool_fetch_product_detail
                self._tools.append(tool_fetch_product_detail)
            except Exception:
                logger.debug("[PRODUCT_SEARCH] Page scraper tool not available")
            # Sprint 196: B2B sourcing tools (already registered via get_product_search_tools()
            # but also available standalone — no-op if already in the list)
            _tool_names = {t.name for t in self._tools}
            from app.core.config import get_settings as _gs196
            _s196 = _gs196()
            if _s196.enable_dealer_search and "tool_dealer_search" not in _tool_names:
                from app.engine.tools.dealer_search_tool import get_dealer_search_tool
                self._tools.append(get_dealer_search_tool())
            if _s196.enable_contact_extraction and "tool_extract_contacts" not in _tool_names:
                from app.engine.tools.contact_extraction_tool import get_contact_extraction_tool
                self._tools.append(get_contact_extraction_tool())
            if _s196.enable_international_search and "tool_international_search" not in _tool_names:
                from app.engine.tools.international_search_tool import get_international_search_tool
                self._tools.append(get_international_search_tool())
            # Sprint 200: Visual product search tool
            if _s196.enable_visual_product_search and "tool_identify_product_from_image" not in _tool_names:
                from app.engine.tools.visual_product_search import get_visual_product_search_tool
                self._tools.append(get_visual_product_search_tool())
        except Exception as e:
            logger.warning("[PRODUCT_SEARCH] Tools init failed: %s", e)

        if self._llm and self._tools:
            self._llm_with_tools = self._llm.bind_tools(self._tools)
        elif self._llm:
            self._llm_with_tools = self._llm

    async def process(self, state: AgentState) -> AgentState:
        """Main entry point from LangGraph."""
        query = state.get("query", "")
        context = state.get("context", {})

        # Get event queue for streaming
        event_queue = None
        bus_id = state.get("_event_bus_id")
        if bus_id:
            from app.engine.multi_agent.graph_streaming import _get_event_queue
            event_queue = _get_event_queue(bus_id)

        # Sprint 200: Pass images for visual product search
        images = state.get("images") or (context.get("images") if context else None)

        # Run ReAct loop
        response, tools_used, thinking, answer_streamed = await self._react_loop(
            query=query,
            context=context,
            event_queue=event_queue,
            thinking_effort=state.get("thinking_effort"),
            images=images,
        )

        if answer_streamed:
            state["_answer_streamed_via_bus"] = True

        state["final_response"] = response
        state["agent_outputs"] = state.get("agent_outputs", {})
        state["agent_outputs"]["product_search"] = response
        state["current_agent"] = "product_search_agent"
        state["tools_used"] = tools_used

        if thinking:
            state["thinking"] = thinking

        return state

    async def _react_loop(
        self,
        query: str,
        context: dict,
        event_queue=None,
        thinking_effort: str = None,
        images: list = None,
    ) -> Tuple[str, List[Dict], Optional[str], bool]:
        """
        ReAct loop for product search.

        Returns:
            (response_text, tools_used, thinking_content, answer_streamed_via_bus)
        """
        if not self._llm:
            return "Xin lỗi, hệ thống tìm kiếm sản phẩm chưa sẵn sàng.", [], None, False

        # Rebuild LLM if effort override
        llm_to_use = self._llm_with_tools
        if thinking_effort and self._llm:
            try:
                from app.engine.multi_agent.agent_config import AgentConfigRegistry
                llm_override = AgentConfigRegistry.get_llm("product_search", effort_override=thinking_effort)
                if llm_override and self._tools:
                    llm_to_use = llm_override.bind_tools(self._tools)
            except Exception:
                pass

        # Event push helpers
        async def _push(evt):
            if event_queue is not None:
                try:
                    event_queue.put_nowait(evt)
                except Exception:
                    pass

        async def _push_thinking_deltas(text: str):
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({"type": "thinking_delta", "content": sub, "node": "product_search_agent"})
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        async def _push_answer_deltas(text: str):
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({"type": "answer_delta", "content": sub, "node": "product_search_agent"})
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        # Build system prompt (Sprint 150: append deep search strategy)
        system_prompt = _SYSTEM_PROMPT + _DEEP_SEARCH_PROMPT

        # Sprint 197: LLM Query Planner pre-step
        try:
            from app.core.config import get_settings as _gs197
            if _gs197().enable_query_planner:
                from app.engine.tools.query_planner import plan_search_queries, format_plan_for_prompt
                await _push({
                    "type": "thinking_start",
                    "content": "Lập kế hoạch tìm kiếm thông minh",
                    "node": "product_search_agent",
                    "summary": f"Phân tích: {query[:50]}",
                })
                _query_plan = await plan_search_queries(query, context)
                if _query_plan:
                    system_prompt += "\n\n" + format_plan_for_prompt(_query_plan)
                    await _push_thinking_deltas(
                        f"\nĐã lập kế hoạch: {_query_plan.intent.value}, "
                        f"{len(_query_plan.sub_queries)} truy vấn tối ưu"
                    )
                    logger.info(
                        "[PRODUCT_SEARCH] Query plan: intent=%s, strategy=%s, %d sub_queries",
                        _query_plan.intent.value,
                        _query_plan.search_strategy.value,
                        len(_query_plan.sub_queries),
                    )
                if event_queue is not None:
                    await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})
        except Exception as _plan_err:
            logger.debug("[PRODUCT_SEARCH] Query planner skipped: %s", _plan_err)

        # Sprint 200: Image routing — instruct agent to use visual search first
        if images and len(images) > 0:
            try:
                from app.core.config import get_settings as _gs200
                if _gs200().enable_visual_product_search:
                    system_prompt += """

## NHẬN DIỆN SẢN PHẨM TỪ ẢNH (Sprint 200)
Người dùng đã gửi ảnh sản phẩm.
BƯỚC 1: Gọi tool_identify_product_from_image với ảnh (image_data = base64) để xác định sản phẩm.
BƯỚC 2: Dùng kết quả (search_keywords) để tìm kiếm trên các sàn TMĐT.
BƯỚC 3: So sánh giá và tổng hợp kết quả.
"""
            except Exception:
                pass

        messages = [SystemMessage(content=system_prompt)]
        # Inject conversation history (last 6 turns — product search is usually standalone)
        lc_messages = context.get("langchain_messages", [])
        if lc_messages:
            messages.extend(lc_messages[-6:])

        # Sprint 200: Build user message — include image if available
        if images and len(images) > 0:
            # Multimodal HumanMessage with image + text
            content_parts = []
            for img in images[:1]:  # Use first image only
                img_data = img.get("data", "") if isinstance(img, dict) else ""
                img_type = img.get("media_type", "image/jpeg") if isinstance(img, dict) else "image/jpeg"
                if img_data:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{img_type};base64,{img_data}"},
                    })
            content_parts.append({"type": "text", "text": query})
            messages.append(HumanMessage(content=content_parts))
        else:
            messages.append(HumanMessage(content=query))

        tools_used = []
        all_thinking = []
        final_response = ""
        answer_streamed = False
        response = None

        # Sprint 200: Preview card emission tracking
        # Sprint 202: Suppress raw previews when curation is active
        _preview_emitted_ids: set = set()
        _preview_card_count = 0
        _curation_active = False
        try:
            from app.core.config import get_settings as _gs200b
            _s200 = _gs200b()
            _preview_enabled = _s200.enable_product_preview_cards
            _preview_max = _s200.product_preview_max_cards
            _curation_active = getattr(_s200, "enable_curated_product_cards", False)
            if _curation_active:
                _preview_enabled = False  # Suppress raw previews; curation emits them later
        except Exception:
            _preview_enabled = True
            _preview_max = 20

        # Sprint 202: Accumulate all tool results for post-loop curation
        _accumulated_products: List[Dict] = []

        # Sprint 150: configurable max iterations
        try:
            from app.core.config import get_settings
            max_iterations = get_settings().product_search_max_iterations
        except Exception:
            max_iterations = _MAX_ITERATIONS_DEFAULT

        for iteration in range(max_iterations):
            # Emit thinking_start
            if event_queue is not None:
                _label = _iteration_label(iteration, tools_used)
                await _push({
                    "type": "thinking_start",
                    "content": _label,
                    "node": "product_search_agent",
                    "summary": f"Tìm kiếm sản phẩm: {query[:50]}",
                })

            # LLM inference (streaming if event queue available)
            if event_queue is not None:
                response = None
                async for chunk in llm_to_use.astream(messages):
                    if response is None:
                        response = chunk
                    else:
                        response = response + chunk
                    # Extract text from chunk for thinking delta
                    text = ""
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text += block.get("text", "")
                                elif isinstance(block, str):
                                    text += block
                    if text:
                        await _push_thinking_deltas(text)
            else:
                response = await llm_to_use.ainvoke(messages)

            if response is None:
                break

            # Check for tool calls
            tool_calls = getattr(response, 'tool_calls', [])
            if not tool_calls:
                # No tools — extract final response
                if event_queue is not None:
                    await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})

                final_response = self._extract_text(response.content)
                thinking_text = self._extract_thinking(response.content)
                if thinking_text:
                    all_thinking.append(thinking_text)

                # Stream answer
                if event_queue is not None and final_response:
                    answer_streamed = True
                    await _push_answer_deltas(final_response)
                break

            # Execute tool calls
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", f"tc_{iteration}")

                # Push tool_call event
                await _push({
                    "type": "tool_call",
                    "content": {"name": tool_name, "args": tool_args, "id": tool_id},
                    "node": "product_search_agent",
                })

                # Execute tool
                matched = next((t for t in self._tools if t.name == tool_name), None)
                try:
                    if matched:
                        result = await asyncio.to_thread(matched.invoke, tool_args)
                    else:
                        result = json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
                except Exception as e:
                    logger.warning("[PRODUCT_SEARCH] Tool %s failed: %s", tool_name, e)
                    result = json.dumps({"error": f"Tool {tool_name} failed: {str(e)[:200]}"}, ensure_ascii=False)

                # Push tool_result event
                await _push({
                    "type": "tool_result",
                    "content": {"name": tool_name, "result": str(result)[:500], "id": tool_id},
                    "node": "product_search_agent",
                })

                # Sprint 153/155: Push browser screenshots if available
                if tool_name.startswith("tool_search_facebook") or tool_name.startswith("tool_search_instagram"):
                    try:
                        from app.engine.search_platforms import get_search_platform_registry
                        _registry = get_search_platform_registry()
                        _platform_id = tool_name.replace("tool_search_", "")
                        _adapter = _registry.get(_platform_id)
                        if _adapter and hasattr(_adapter, "get_last_screenshots"):
                            for _shot in _adapter.get_last_screenshots():
                                await _push({
                                    "type": "browser_screenshot",
                                    "content": _shot,
                                    "node": "product_search_agent",
                                })
                    except Exception:
                        pass

                # Post-tool acknowledgment
                _ack = _TOOL_ACK.get(tool_name, f"Đã nhận kết quả từ {tool_name}.")
                await _push_thinking_deltas(f"\n\n{_ack}")

                # Add to message history (OBSERVE step)
                # Sprint 153: Truncate tool results to prevent context window overflow
                result_str = str(result)[:5000]
                messages.append(AIMessage(content="", tool_calls=[tool_call]))
                messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))

                tools_used.append({"name": tool_name, "args": tool_args, "iteration": iteration})

                # Sprint 200: Emit product preview cards in real-time
                if _preview_enabled and event_queue is not None:
                    preview_events = _emit_product_previews(
                        tool_name=tool_name,
                        result_str=result_str,
                        emitted_ids=_preview_emitted_ids,
                        max_cards=_preview_max,
                        current_count=_preview_card_count,
                    )
                    for pe in preview_events:
                        await _push(pe)
                        _preview_card_count += 1

                # Sprint 202: Accumulate products for post-loop curation
                if _curation_active and tool_name in _PRODUCT_RESULT_TOOLS:
                    try:
                        _parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
                        if isinstance(_parsed, dict):
                            _platform = _parsed.get("platform", tool_name.replace("tool_search_", ""))
                            for _prod in (_parsed.get("results", []) or []):
                                if isinstance(_prod, dict):
                                    _prod.setdefault("platform", _platform)
                                    _accumulated_products.append(_prod)
                    except (json.JSONDecodeError, Exception):
                        pass

            # Close thinking block AFTER tools (Sprint 146b pattern)
            if event_queue is not None:
                await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})

        # If no final response yet (loop exhausted), do final generation
        if not final_response and response is not None:
            if event_queue is not None:
                await _push({
                    "type": "thinking_start",
                    "content": "Tổng hợp kết quả cuối cùng",
                    "node": "product_search_agent",
                })

            # Use base LLM (no tools) for final synthesis
            if event_queue is not None:
                final_chunks = []
                async for chunk in self._llm.astream(messages):
                    text = ""
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text += block.get("text", "")
                    if text:
                        final_chunks.append(text)
                        await _push_answer_deltas(text)
                final_response = "".join(final_chunks)
                answer_streamed = True

                await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})
            else:
                final_gen = await self._llm.ainvoke(messages)
                final_response = self._extract_text(final_gen.content)

        # Sprint 202: Post-loop curation for legacy ReAct path
        if _curation_active and _accumulated_products and event_queue is not None:
            try:
                from app.engine.multi_agent.subagents.search.curation import curate_with_llm
                from app.core.config import get_settings as _gs202c
                _s202c = _gs202c()
                _max_c = getattr(_s202c, "curated_product_max_cards", 8)
                _tier_c = getattr(_s202c, "curated_product_llm_tier", "light")

                # Deduplicate by link
                _seen_links: set = set()
                _deduped: List[Dict] = []
                for _p in _accumulated_products:
                    _lnk = _p.get("link", "")
                    if _lnk and _lnk in _seen_links:
                        continue
                    if _lnk:
                        _seen_links.add(_lnk)
                    _deduped.append(_p)

                selection = await curate_with_llm(
                    query=query, products=_deduped, max_curated=_max_c, llm_tier=_tier_c,
                )
                curated_list = []
                if selection and selection.selected:
                    for pick in selection.selected:
                        if 0 <= pick.index < len(_deduped):
                            prod = _deduped[pick.index].copy()
                            prod["_highlight"] = pick.highlight
                            prod["_relevance_score"] = pick.relevance_score
                            curated_list.append(prod)

                if not curated_list:
                    curated_list = _deduped[:_max_c]

                # Emit curated previews
                for i, prod in enumerate(curated_list):
                    title = prod.get("title") or prod.get("name", "")
                    if not title:
                        continue
                    link = prod.get("link") or prod.get("url", "")
                    pid = f"curated_{hash(link) % 100000}_{i}" if link else f"curated_{i}"
                    metadata = {
                        "price": prod.get("price", ""),
                        "platform": prod.get("platform", ""),
                        "seller": prod.get("seller", ""),
                        "rating": prod.get("rating"),
                        "sold_count": prod.get("sold_count"),
                        "delivery": prod.get("delivery", ""),
                        "extracted_price": prod.get("extracted_price"),
                        "location": prod.get("location", ""),
                    }
                    if prod.get("_highlight"):
                        metadata["highlight"] = prod["_highlight"]
                    if prod.get("_relevance_score") is not None:
                        metadata["relevance_score"] = prod["_relevance_score"]
                    await _push({
                        "type": "preview",
                        "content": {
                            "preview_type": "product",
                            "preview_id": pid,
                            "title": title[:120],
                            "snippet": (prod.get("snippet") or prod.get("description", ""))[:150],
                            "url": link,
                            "image_url": prod.get("image") or prod.get("image_url") or prod.get("thumbnail", ""),
                            "metadata": metadata,
                        },
                        "node": "product_search_agent",
                    })
            except Exception as _cur_exc:
                logger.warning("[PRODUCT_SEARCH] Post-loop curation failed: %s", _cur_exc)

        combined_thinking = "\n\n".join(all_thinking) if all_thinking else None
        return final_response, tools_used, combined_thinking, answer_streamed

    @staticmethod
    def _extract_text(content) -> str:
        """Extract text from LLM response content (handles Gemini block format)."""
        if isinstance(content, str):
            # Strip thinking tags if present
            from app.services.output_processor import extract_thinking_from_response
            text, _ = extract_thinking_from_response(content)
            return text.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return " ".join(parts).strip()
        return str(content).strip()

    @staticmethod
    def _extract_thinking(content) -> str:
        """Extract thinking content from LLM response."""
        if isinstance(content, str):
            from app.services.output_processor import extract_thinking_from_response
            _, thinking = extract_thinking_from_response(content)
            return thinking or ""
        return ""


# =============================================================================
# Singleton
# =============================================================================

_product_search_node: Optional[ProductSearchAgentNode] = None
_node_lock = threading.Lock()


def get_product_search_agent_node() -> ProductSearchAgentNode:
    """Get or create ProductSearchAgentNode singleton (thread-safe)."""
    global _product_search_node
    if _product_search_node is None:
        with _node_lock:
            if _product_search_node is None:
                _product_search_node = ProductSearchAgentNode()
    return _product_search_node
