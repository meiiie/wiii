"""Sprint 202: LLM-Curated Product Cards — "Kết Quả Sạch".

Selects top 3-8 products from raw search results using LLM structured output.
Matches industry standard (ChatGPT Shopping, Perplexity Pro Picks).

Gate: ``enable_curated_product_cards=False`` (default off).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.engine.multi_agent.lane_timeout_policy import (
    resolve_product_curation_timeout_impl,
)

logger = logging.getLogger(__name__)

# Max chars for compact product summaries sent to LLM
_MAX_PRODUCT_TEXT_CHARS = 100_000  # Sprint 202b: effectively unlimited — LLM context is the real cap


# ── Pydantic schemas (structured output) ────────────────────────────


class CuratedProduct(BaseModel):
    """A single LLM-selected product pick."""

    index: int = Field(
        description="0-based index into the deduped product list",
    )
    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="0-1 relevance to user query",
    )
    reason: str = Field(
        description="Vietnamese — why this product was selected",
    )
    highlight: str = Field(
        description="1-line badge, e.g. 'Giá tốt nhất', 'Chính hãng', 'Bán chạy'",
    )

    @field_validator("relevance_score", mode="before")
    @classmethod
    def _clamp_score(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, v))


class CuratedProductSelection(BaseModel):
    """LLM output: curated product picks."""

    selected: List[CuratedProduct] = Field(
        description="3-8 curated product picks, ordered by relevance",
    )
    reasoning: str = Field(
        default="",
        description="Overall reasoning for the selection (Vietnamese)",
    )
    total_evaluated: int = Field(
        default=0,
        description="How many products the LLM evaluated",
    )


# ── Curation prompt ─────────────────────────────────────────────────

_CURATION_PROMPT = """Bạn là chuyên gia lọc sản phẩm. Từ danh sách kết quả tìm kiếm thô, chọn ra {max_curated} sản phẩm TỐT NHẤT cho người dùng.

## TIÊU CHÍ LỌC (quan trọng → ít quan trọng)
1. **Đúng sản phẩm**: Đúng loại, thương hiệu, thông số mà người dùng yêu cầu
2. **Đa dạng nguồn**: Từ nhiều sàn/website khác nhau — PHẢI chọn từ ít nhất 2-3 nguồn khác nhau
3. **Đa dạng giá**: Mix giá rẻ / trung bình / cao cấp để người dùng có lựa chọn
4. **Giá hợp lý**: Loại bỏ giá scam (quá rẻ vô lý) và giá chặt (quá đắt)
5. **Uy tín nguồn**: Rating cao, lượt bán nhiều, shop verified
6. **Đủ thông tin**: Có giá, có hình, có link — nhưng sản phẩm giá tốt từ đại lý KHÔNG CẦN đầy đủ

## QUERY CỦA NGƯỜI DÙNG
{query}

## DANH SÁCH SẢN PHẨM ({total_products} sản phẩm)
{product_text}

## YÊU CẦU
- Chọn tối đa {max_curated} sản phẩm (tối thiểu 3 nếu đủ)
- Mỗi sản phẩm cần: index (0-based), relevance_score (0-1), reason (tiếng Việt), highlight (badge ngắn)
- Highlight ví dụ: "Giá tốt nhất", "Chính hãng", "Bán chạy", "Uy tín cao", "Đánh giá tốt", "Giá sỉ"
- Trả về JSON theo schema CuratedProductSelection
"""


def _build_compact_product_text(products: List[Dict[str, Any]], max_chars: int = _MAX_PRODUCT_TEXT_CHARS) -> str:
    """Build compact product summary text for LLM input."""
    lines = []
    for i, p in enumerate(products):
        title = (p.get("title") or p.get("name", ""))[:80]
        price = p.get("price", "")
        platform = p.get("platform", "")
        rating = p.get("rating", "")
        sold = p.get("sold_count", "")
        seller = p.get("seller", "")

        parts = [f"[{i}] {title}"]
        if price:
            parts.append(f"Giá: {price}")
        # Sprint 202b: Always include platform so LLM sees source diversity
        parts.append(f"Sàn: {platform or 'web'}")
        if rating:
            parts.append(f"Rating: {rating}")
        if sold:
            parts.append(f"Đã bán: {sold}")
        if seller:
            parts.append(f"Shop: {seller[:30]}")

        line = " | ".join(parts)
        lines.append(line)

        # Check total size
        total = "\n".join(lines)
        if len(total) > max_chars:
            lines.append(f"... và {len(products) - i - 1} sản phẩm khác")
            break

    return "\n".join(lines)


async def curate_with_llm(
    query: str,
    products: List[Dict[str, Any]],
    max_curated: int = 8,
    llm_tier: str = "light",
    timeout_seconds: float = 10.0,
    provider_override: str | None = None,
    requested_model: str | None = None,
) -> Optional[CuratedProductSelection]:
    """Call LLM to curate top products from raw results.

    Returns CuratedProductSelection or None on failure.
    Uses structured output (``with_structured_output``).
    """
    if not products:
        return None

    product_text = _build_compact_product_text(products)
    prompt = _CURATION_PROMPT.format(
        query=query,
        max_curated=max_curated,
        total_products=len(products),
        product_text=product_text,
    )

    try:
        from app.engine.multi_agent.agent_config import AgentConfigRegistry

        # Get LLM for the specified tier
        llm = AgentConfigRegistry.get_llm(
            "product_search",
            provider_override=provider_override,
            requested_model=requested_model,
        )
        if not llm:
            logger.warning("[CURATE] No LLM available for curation")
            return None

        provider_name = str(getattr(llm, "_wiii_provider_name", "") or "").strip().lower() or None
        effective_timeout = resolve_product_curation_timeout_impl(
            provider_name=provider_name,
            query=query,
            total_products=len(products),
            requested_timeout=timeout_seconds,
        )

        from app.services.structured_invoke_service import StructuredInvokeService

        from app.engine.messages import Message
        from app.engine.messages_adapters import to_openai_dict

        chat_messages = [
            Message(role="system", content="Bạn là trợ lý lọc sản phẩm. Trả lời JSON theo schema được yêu cầu."),
            Message(role="user", content=prompt),
        ]

        result = await asyncio.wait_for(
            StructuredInvokeService.ainvoke(
                llm=llm,
                schema=CuratedProductSelection,
                payload=[to_openai_dict(m) for m in chat_messages],
                tier="moderate",
                timeout_profile="structured",
            ),
            timeout=effective_timeout,
        )

        if not isinstance(result, CuratedProductSelection):
            logger.warning("[CURATE] LLM returned unexpected type: %s", type(result))
            return None

        # Validate indices are in bounds
        valid_selected = []
        for item in result.selected:
            if 0 <= item.index < len(products):
                valid_selected.append(item)
            else:
                logger.debug("[CURATE] Skipping out-of-bounds index %d (max %d)", item.index, len(products) - 1)

        if not valid_selected:
            logger.warning("[CURATE] All selected indices were invalid")
            return None

        result.selected = valid_selected[:max_curated]
        result.total_evaluated = len(products)
        return result

    except asyncio.TimeoutError:
        logger.warning("[CURATE] LLM curation timed out after %.1fs", effective_timeout if 'effective_timeout' in locals() else timeout_seconds)
        return None
    except Exception as exc:
        logger.warning("[CURATE] LLM curation failed: %s", exc)
        return None
