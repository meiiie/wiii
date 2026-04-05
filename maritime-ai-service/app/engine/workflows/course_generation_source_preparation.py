"""Source preparation helpers for course-generation outline prompts.

This module compacts large source markdown into a provider-aware, page-mapped
document map before we ask the model to build a course outline. The goal is to
keep outline generation resilient across failover providers with smaller
effective context budgets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import re
from typing import Optional

from app.core.config import settings
from app.engine.context_manager import get_budget_manager
from app.engine.llm_factory import ThinkingTier
from app.engine.llm_pool import (
    FAILOVER_MODE_AUTO,
    FAILOVER_MODE_PINNED,
    LLMPool,
)

logger = logging.getLogger(__name__)

_PAGE_MARKER_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET_LINE_RE = re.compile(r"^([-*]|[0-9]+[.)]|[a-zA-Z][.)])\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+")

# Conservative "source-only" budgets, not full model context sizes.
# These values are intentionally smaller than vendor marketing windows to keep
# outline generation stable under failover and schema overhead.
_SOURCE_TOKEN_BUDGET_BY_PROVIDER: dict[str, dict[str, int]] = {
    "google": {"deep": 16000, "moderate": 12000, "light": 8000},
    "zhipu": {"deep": 6000, "moderate": 5000, "light": 4000},
    "openai": {"deep": 7000, "moderate": 6000, "light": 4500},
    "openrouter": {"deep": 7000, "moderate": 6000, "light": 4500},
    "ollama": {"deep": 5000, "moderate": 4000, "light": 3000},
}
_DEFAULT_SOURCE_BUDGET = {"deep": 6000, "moderate": 5000, "light": 4000}
_CHARS_PER_TOKEN = 4


@dataclass(slots=True)
class OutlineSourceSection:
    """One structural chunk extracted from the source markdown."""

    title: str
    level: int
    start_page: int
    end_page: int
    content: str


@dataclass(slots=True)
class PreparedOutlineSource:
    """Prepared source artifact used to build the outline prompt."""

    rendered_markdown: str
    mode: str
    original_chars: int
    prepared_chars: int
    original_tokens_estimate: int
    prepared_tokens_estimate: int
    token_budget: int
    candidate_providers: tuple[str, ...]
    total_sections: int
    included_sections: int
    truncated_sections: int

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


def prepare_outline_source(
    *,
    markdown: str,
    tier: str = ThinkingTier.DEEP.value,
    provider: Optional[str] = None,
    failover_mode: str = FAILOVER_MODE_AUTO,
) -> PreparedOutlineSource:
    """Prepare source markdown for outline generation.

    Produces a deterministic, page-aware document map that stays under a
    provider-aware token budget whenever possible.
    """

    budget_manager = get_budget_manager()
    normalized_tier = _normalize_tier(tier)
    candidate_providers = _resolve_candidate_providers(
        provider=provider,
        failover_mode=failover_mode,
        tier=normalized_tier,
    )
    token_budget = _resolve_source_budget_tokens(
        candidate_providers,
        tier=normalized_tier,
    )
    original_tokens = budget_manager.estimate_tokens(markdown)
    original_chars = len(markdown or "")

    if not markdown:
        return PreparedOutlineSource(
            rendered_markdown="",
            mode="empty",
            original_chars=0,
            prepared_chars=0,
            original_tokens_estimate=0,
            prepared_tokens_estimate=0,
            token_budget=token_budget,
            candidate_providers=candidate_providers,
            total_sections=0,
            included_sections=0,
            truncated_sections=0,
        )

    if original_tokens <= token_budget:
        return PreparedOutlineSource(
            rendered_markdown=markdown,
            mode="full",
            original_chars=original_chars,
            prepared_chars=original_chars,
            original_tokens_estimate=original_tokens,
            prepared_tokens_estimate=original_tokens,
            token_budget=token_budget,
            candidate_providers=candidate_providers,
            total_sections=0,
            included_sections=0,
            truncated_sections=0,
        )

    sections = _extract_sections(markdown)
    if not sections:
        sections = [_build_fallback_section(markdown)]

    compacted = _render_compacted_source(
        sections,
        token_budget=token_budget,
        candidate_providers=candidate_providers,
    )
    compacted_tokens = budget_manager.estimate_tokens(compacted)

    if compacted_tokens <= token_budget:
        return PreparedOutlineSource(
            rendered_markdown=compacted,
            mode="chunk_compact",
            original_chars=original_chars,
            prepared_chars=len(compacted),
            original_tokens_estimate=original_tokens,
            prepared_tokens_estimate=compacted_tokens,
            token_budget=token_budget,
            candidate_providers=candidate_providers,
            total_sections=len(sections),
            included_sections=len(sections),
            truncated_sections=len(sections),
        )

    indexed = _render_heading_index(
        sections,
        token_budget=token_budget,
        candidate_providers=candidate_providers,
    )
    indexed_tokens = budget_manager.estimate_tokens(indexed)

    if indexed_tokens > token_budget:
        indexed = _trim_to_budget(indexed, token_budget, budget_manager)
        indexed_tokens = budget_manager.estimate_tokens(indexed)

    return PreparedOutlineSource(
        rendered_markdown=indexed,
        mode="heading_index",
        original_chars=original_chars,
        prepared_chars=len(indexed),
        original_tokens_estimate=original_tokens,
        prepared_tokens_estimate=indexed_tokens,
        token_budget=token_budget,
        candidate_providers=candidate_providers,
        total_sections=len(sections),
        included_sections=len(sections),
        truncated_sections=len(sections),
    )


def _normalize_tier(tier: str | ThinkingTier | None) -> str:
    if isinstance(tier, ThinkingTier):
        return tier.value
    normalized = str(tier or ThinkingTier.DEEP.value).strip().lower()
    if normalized in _DEFAULT_SOURCE_BUDGET:
        return normalized
    return ThinkingTier.DEEP.value


def _resolve_candidate_providers(
    *,
    provider: Optional[str],
    failover_mode: str,
    tier: str,
) -> tuple[str, ...]:
    normalized_provider = (provider or "").strip().lower() or None
    if normalized_provider and failover_mode == FAILOVER_MODE_PINNED:
        return (normalized_provider,)

    try:
        route = LLMPool.resolve_runtime_route(
            normalized_provider,
            tier,
            failover_mode=failover_mode,
        )
        providers: list[str] = []
        if route.provider:
            providers.append(route.provider)
        if failover_mode != FAILOVER_MODE_PINNED and route.fallback_provider:
            providers.append(route.fallback_provider)
        if providers:
            return tuple(dict.fromkeys(providers))
    except Exception as exc:
        logger.debug(
            "[COURSE_GEN] Could not resolve runtime route for source budgeting: %s",
            exc,
        )

    configured_primary = str(getattr(settings, "llm_provider", "google") or "google").strip().lower()
    configured_chain = list(getattr(settings, "llm_failover_chain", ["google", "zhipu"]))
    providers: list[str] = []
    if normalized_provider:
        providers.append(normalized_provider)
    elif configured_primary:
        providers.append(configured_primary)
    if failover_mode != FAILOVER_MODE_PINNED:
        for name in configured_chain:
            normalized = str(name or "").strip().lower()
            if normalized and normalized not in providers:
                providers.append(normalized)
    return tuple(providers or ["google"])


def _resolve_source_budget_tokens(
    candidate_providers: tuple[str, ...],
    *,
    tier: str,
) -> int:
    budgets: list[int] = []
    for provider in candidate_providers:
        provider_budget = _SOURCE_TOKEN_BUDGET_BY_PROVIDER.get(provider, _DEFAULT_SOURCE_BUDGET)
        budgets.append(provider_budget.get(tier, _DEFAULT_SOURCE_BUDGET[tier]))
    if not budgets:
        return _DEFAULT_SOURCE_BUDGET[tier]
    return min(budgets)


def _extract_sections(markdown: str) -> list[OutlineSourceSection]:
    sections: list[OutlineSourceSection] = []
    current_page = 1
    current_title = "Mở đầu tài liệu"
    current_level = 0
    current_start_page = 1
    current_lines: list[str] = []
    saw_heading = False

    def flush(end_page: int) -> None:
        nonlocal current_lines, current_title, current_level, current_start_page
        content = "\n".join(current_lines).strip()
        if not content:
            current_lines = []
            return
        sections.append(
            OutlineSourceSection(
                title=current_title,
                level=current_level,
                start_page=current_start_page,
                end_page=max(current_start_page, end_page),
                content=content,
            )
        )
        current_lines = []

    for raw_line in markdown.splitlines():
        page_match = _PAGE_MARKER_RE.search(raw_line)
        if page_match:
            current_page = int(page_match.group(1))

        heading_match = _HEADING_RE.match(raw_line.strip())
        if heading_match:
            flush(current_page)
            current_level = len(heading_match.group(1))
            current_title = heading_match.group(2).strip()
            current_start_page = current_page
            current_lines = [raw_line]
            saw_heading = True
            continue

        if not saw_heading and not current_lines:
            current_start_page = current_page
        current_lines.append(raw_line)

    flush(current_page)

    return [section for section in sections if section.content.strip()]


def _build_fallback_section(markdown: str) -> OutlineSourceSection:
    last_page = 1
    for match in _PAGE_MARKER_RE.finditer(markdown):
        last_page = max(last_page, int(match.group(1)))
    return OutlineSourceSection(
        title="Toàn bộ tài liệu",
        level=1,
        start_page=1,
        end_page=last_page,
        content=markdown,
    )


def _render_compacted_source(
    sections: list[OutlineSourceSection],
    *,
    token_budget: int,
    candidate_providers: tuple[str, ...],
) -> str:
    max_chars = max(token_budget * _CHARS_PER_TOKEN, 1200)
    section_count = max(1, len(sections))
    per_section_chars = max(360, min(1400, max_chars // section_count))

    lines = [
        "[PREPARED_DOCUMENT_MAP]",
        "mode=chunk_compact",
        f"providers={','.join(candidate_providers) or 'google'}",
        f"section_count={len(sections)}",
        "Use headings and page ranges as the structural truth when building the outline.",
        "",
    ]

    for index, section in enumerate(sections, start=1):
        excerpt = _summarize_section_content(section.content, max_chars=per_section_chars)
        lines.append(
            f"## {index}. {section.title} (pages {section.start_page}-{section.end_page})"
        )
        lines.append(excerpt)
        lines.append("")

    return "\n".join(lines).strip()


def _render_heading_index(
    sections: list[OutlineSourceSection],
    *,
    token_budget: int,
    candidate_providers: tuple[str, ...],
) -> str:
    max_chars = max(token_budget * _CHARS_PER_TOKEN, 800)
    section_count = max(1, len(sections))
    per_section_chars = max(80, min(280, max_chars // section_count))

    lines = [
        "[PREPARED_DOCUMENT_MAP]",
        "mode=heading_index",
        f"providers={','.join(candidate_providers) or 'google'}",
        f"section_count={len(sections)}",
        "Source is compressed to a heading index because the original document exceeded the safe provider budget.",
        "",
    ]

    for index, section in enumerate(sections, start=1):
        excerpt = _heading_index_excerpt(section.content, max_chars=per_section_chars)
        line = (
            f"- {index}. {section.title} | pages {section.start_page}-{section.end_page}"
        )
        if excerpt:
            line = f"{line} | {excerpt}"
        lines.append(line)

    return "\n".join(lines).strip()


def _summarize_section_content(content: str, *, max_chars: int) -> str:
    cleaned_lines = _meaningful_lines(content)
    if not cleaned_lines:
        return "(không có nội dung trích yếu)"

    heading_line = cleaned_lines[0] if _HEADING_RE.match(cleaned_lines[0]) else None
    body_lines = cleaned_lines[1:] if heading_line else cleaned_lines

    selected: list[str] = []
    paragraphs = _paragraph_candidates(body_lines)
    for paragraph in paragraphs[:2]:
        if paragraph not in selected:
            selected.append(paragraph)

    for line in body_lines:
        if _BULLET_LINE_RE.match(line) and line not in selected:
            selected.append(line)
        if len("\n".join(selected)) >= max_chars:
            break

    if paragraphs:
        tail = paragraphs[-1]
        if tail not in selected:
            selected.append(tail)

    if not selected:
        selected = body_lines[:4]

    text = "\n".join(selected).strip()
    return _truncate_text(text, max_chars=max_chars)


def _heading_index_excerpt(content: str, *, max_chars: int) -> str:
    cleaned_lines = _meaningful_lines(content)
    body_lines = cleaned_lines[1:] if cleaned_lines and _HEADING_RE.match(cleaned_lines[0]) else cleaned_lines
    if not body_lines:
        return ""

    priority_lines: list[str] = []
    for line in body_lines:
        if _BULLET_LINE_RE.match(line):
            priority_lines.append(line)
    if not priority_lines:
        priority_lines = body_lines[:2]

    text = " ".join(priority_lines)
    if len(text) <= max_chars:
        return text

    sentences = _SENTENCE_SPLIT_RE.split(text)
    excerpt = ""
    for sentence in sentences:
        candidate = f"{excerpt} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        excerpt = candidate
    if excerpt:
        return excerpt
    return _truncate_text(text, max_chars=max_chars)


def _meaningful_lines(content: str) -> list[str]:
    lines: list[str] = []
    for raw_line in content.splitlines():
        if _PAGE_MARKER_RE.search(raw_line):
            continue
        cleaned = " ".join(raw_line.strip().split())
        if not cleaned:
            continue
        lines.append(cleaned)
    return lines


def _paragraph_candidates(lines: list[str]) -> list[str]:
    if not lines:
        return []

    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if _BULLET_LINE_RE.match(line):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            paragraphs.append(line)
            continue

        if len(" ".join(current + [line])) > 320:
            if current:
                paragraphs.append(" ".join(current).strip())
            current = [line]
            continue

        current.append(line)

    if current:
        paragraphs.append(" ".join(current).strip())

    return [paragraph for paragraph in paragraphs if paragraph]


def _truncate_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    suffix = " ..."
    cutoff = max(1, max_chars - len(suffix))
    return text[:cutoff].rstrip() + suffix


def _trim_to_budget(text: str, token_budget: int, budget_manager) -> str:
    if budget_manager.estimate_tokens(text) <= token_budget:
        return text

    max_chars = max(16, token_budget * _CHARS_PER_TOKEN)
    trimmed = _truncate_text(text, max_chars=max_chars)

    while budget_manager.estimate_tokens(trimmed) > token_budget and len(trimmed) > 16:
        max_chars = max(16, len(trimmed) - _CHARS_PER_TOKEN)
        trimmed = _truncate_text(text, max_chars=max_chars)

    return trimmed
