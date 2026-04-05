"""
EXPAND prompt — generates full chapter content from relevant markdown sections.

Used by Node 2 (EXPAND) of the course generation workflow.
Pydantic schema: models/course_generation.py → ChapterContentSchema
Design spec v2.0 (2026-03-22). Expert: Flash tier, not Pro.
"""

import json


def build_expand_prompt(
    chapter: dict,
    source_content: str,
    language: str = "vi",
) -> str:
    """Build the EXPAND prompt for one chapter."""
    lang_instruction = "Nội dung tiếng Việt" if language == "vi" else "Content in English"
    lessons_json = json.dumps(chapter.get("lessons", []), ensure_ascii=False, indent=2)

    return f"""Tạo nội dung chi tiết cho chương sau của khóa học hàng hải.

CHƯƠNG: {chapter['title']}
MÔ TẢ: {chapter.get('description', '')}
THỨ TỰ: {chapter.get('orderIndex', 0)}

BÀI HỌC CẦN TẠO (từ outline đã duyệt):
{lessons_json}

NỘI DUNG GỐC TỪ TÀI LIỆU:
{source_content}

Quy tắc:
- Mỗi section type=TEXT phải có content HTML hoàn chỉnh (<p>, <h3>, <ul>, <table> tags)
- Giữ nguyên thông tin chính xác từ tài liệu gốc — KHÔNG thêm thông tin sai
- Thêm giải thích, ví dụ minh họa phù hợp ngữ cảnh hàng hải Việt Nam
- Giữ nguyên thuật ngữ chuyên ngành (SOLAS, COLREG, ISM Code, MARPOL...)
- Section type=QUIZ_PLACEHOLDER: chỉ đánh dấu vị trí, content=null
- Mỗi lesson nên có 2-5 sections
- {lang_instruction}

OUTPUT: ChapterContent JSON theo schema. Chỉ trả JSON, không giải thích."""
