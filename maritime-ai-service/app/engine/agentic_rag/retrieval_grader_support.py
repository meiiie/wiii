"""Support helpers for RetrievalGrader batch grading and feedback."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.core.constants import (
    MAX_CONTENT_SNIPPET_LENGTH,
    MAX_DOCUMENT_PREVIEW_LENGTH,
)
from app.engine.agentic_rag.runtime_llm_socket import (
    ainvoke_agentic_rag_llm,
    make_agentic_rag_messages,
)
from app.engine.llm_factory import ThinkingTier
logger = logging.getLogger(__name__)


async def batch_grade_structured_impl(
    *,
    llm,
    threshold: float,
    query: str,
    documents: List[Dict[str, Any]],
    docs_text: str,
    prompt: str,
    document_grade_cls,
):
    """Batch grade using structured output."""
    from app.engine.structured_schemas import BatchDocGrades

    messages = make_agentic_rag_messages(
        system="Grade document relevance for each document.",
        user=prompt.format(query=query, documents=docs_text),
    )

    from app.services.structured_invoke_service import StructuredInvokeService

    result = await StructuredInvokeService.ainvoke(
        llm=llm,
        schema=BatchDocGrades,
        payload=messages,
        tier="moderate",
    )
    grades = []
    for item in result.grades:
        if item.doc_index < len(documents):
            doc = documents[item.doc_index]
            doc_id = doc.get("id", doc.get("node_id", f"doc_{item.doc_index}"))
            content = doc.get("content", doc.get("text", ""))[
                :MAX_CONTENT_SNIPPET_LENGTH
            ]
            grades.append(
                document_grade_cls(
                    document_id=doc_id,
                    content_preview=content,
                    score=item.score,
                    is_relevant=item.score >= threshold,
                    reason=item.reason,
                )
            )

    logger.info("[GRADER] Batch graded %d docs via structured output", len(grades))
    return grades


async def batch_grade_legacy_impl(
    *,
    llm,
    query: str,
    documents: List[Dict[str, Any]],
    docs_text: str,
    prompt: str,
    parse_batch_response,
):
    """Batch grade using legacy JSON parsing."""
    messages = make_agentic_rag_messages(
        system="Grade document relevance. Return only valid JSON array.",
        user=prompt.format(query=query, documents=docs_text),
    )

    response = await ainvoke_agentic_rag_llm(
        llm=llm,
        messages=messages,
        tier=ThinkingTier.MODERATE,
        component="RetrievalGraderBatchLegacy",
    )
    grades = parse_batch_response(response.content, documents)
    logger.info("[GRADER] Batch graded %d docs in 1 LLM call (SOTA)", len(grades))
    return grades


async def sequential_grade_documents_impl(
    *,
    query: str,
    documents: List[Dict[str, Any]],
    grade_document,
):
    """Fallback sequential grading when batch grading fails."""
    grades = []
    for doc in documents:
        grades.append(await grade_document(query, doc))
    return grades


def parse_batch_response_impl(
    *,
    response,
    documents: List[Dict[str, Any]],
    threshold: float,
    document_grade_cls,
    rule_based_grade,
):
    """Parse batch grading JSON response with fallback to rule-based grading."""
    from app.services.output_processor import extract_thinking_from_response

    text_content, _ = extract_thinking_from_response(response)
    result = text_content.strip()

    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    result = result.strip()

    try:
        data = json.loads(result)
        grades = []
        for item in data:
            doc_idx = item.get("doc_index", 0)
            if doc_idx < len(documents):
                doc = documents[doc_idx]
                doc_id = doc.get("id", doc.get("node_id", f"doc_{doc_idx}"))
                content = doc.get("content", doc.get("text", ""))[
                    :MAX_CONTENT_SNIPPET_LENGTH
                ]
                score = float(item.get("score", 5.0))
                grades.append(
                    document_grade_cls(
                        document_id=doc_id,
                        content_preview=content,
                        score=score,
                        is_relevant=score >= threshold,
                        reason=item.get("reason", "Batch graded"),
                    )
                )
        return grades
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse batch response: %s", exc)
        return [
            rule_based_grade(
                "",
                doc.get("id", doc.get("node_id", "unknown")),
                doc.get("content", doc.get("text", ""))[
                    :MAX_DOCUMENT_PREVIEW_LENGTH
                ],
            )
            for doc in documents
        ]


def build_feedback_direct_impl(
    *,
    avg_score: float,
    relevant_count: int,
    total: int,
    issues: List[str],
):
    """Build zero-latency direct feedback text."""
    unique_issues = list(dict.fromkeys(issues))[:3]
    issues_text = (
        "; ".join(unique_issues)
        if unique_issues
        else "Documents không trực tiếp trả lời query"
    )

    if avg_score < 3.0:
        severity = "Rất thấp"
        suggestion = (
            "Thử sử dụng thuật ngữ hàng hải chuẩn (SOLAS, COLREGs, MARPOL)"
        )
    elif avg_score < 5.0:
        severity = "Thấp"
        suggestion = "Thêm từ khóa cụ thể hoặc diễn đạt lại câu hỏi"
    else:
        severity = "Trung bình"
        suggestion = "Cân nhắc thêm context hoặc phạm vi cụ thể hơn"

    return (
        f"Độ liên quan {severity} ({avg_score:.1f}/10, {relevant_count}/{total} docs). "
        f"Vấn đề: {issues_text[:200]}. "
        f"Gợi ý: {suggestion}"
    )


async def generate_feedback_impl(
    *,
    llm,
    query: str,
    avg_score: float,
    relevant_count: int,
    total: int,
    issues: List[str],
    prompt: str,
):
    """Generate feedback via LLM, with plain fallback when unavailable."""
    if not llm:
        return f"Low relevance ({avg_score:.1f}/10). Try more specific keywords."

    try:
        messages = make_agentic_rag_messages(
            user=prompt.format(
                    query=query,
                    avg_score=f"{avg_score:.1f}",
                    relevant_count=relevant_count,
                    total=total,
                    issues="; ".join(issues[:3])
                    if issues
                    else "Documents không trực tiếp trả lời query",
            ),
        )

        response = await ainvoke_agentic_rag_llm(
            llm=llm,
            messages=messages,
            tier=ThinkingTier.MODERATE,
            component="RetrievalGraderFeedback",
        )
        from app.services.output_processor import extract_thinking_from_response

        text_content, _ = extract_thinking_from_response(response.content)
        return text_content.strip()
    except Exception as exc:
        logger.warning("Feedback generation failed: %s", exc)
        return f"Low relevance ({avg_score:.1f}/10). Try more specific keywords."
