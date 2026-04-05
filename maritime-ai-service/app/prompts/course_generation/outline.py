"""
OUTLINE prompt for course generation.

This prompt may receive either the full converted markdown or a prepared
document map that was compacted to stay inside a safe provider budget.
"""


def build_outline_prompt(
    markdown: str,
    language: str = "vi",
    target_chapters: int | None = None,
    teacher_prompt: str = "",
    source_mode: str = "full",
) -> str:
    """Build the outline prompt from source markdown or a prepared map."""

    lang_instruction = "Noi dung tieng Viet" if language == "vi" else "Content in English"
    chapter_hint = f"Tao khoang {target_chapters} chuong." if target_chapters else ""
    prepared_source_hint = (
        "- Tai lieu ben duoi da duoc co dong theo nguong context an toan cua provider. Hay coi heading, page range, key bullet va PREPARED_DOCUMENT_MAP la cau truc goc dang tin cay."
        if source_mode != "full"
        else ""
    )

    return f"""Ban la chuyen gia thiet ke khoa hoc hang hai voi 20 nam kinh nghiem.

Tu tai lieu duoi day, tao course outline theo JSON schema.

Quy tac:
- Moi chapter tuong ung voi 1 phan lon cua tai lieu (Chuong, Part, Section)
- Moi lesson la 1 bai hoc 20-45 phut, focused vao 1 chu de
- Danh dau vi tri nen co quiz bang lesson type "QUIZ" (khong tao noi dung quiz)
- Giu nguyen thuat ngu chuyen nganh hang hai (SOLAS, COLREG, ISM Code, MARPOL...)
- {lang_instruction}
- Them sourcePages mapping cho moi chapter de truy xuat noi dung goc khi generate
- dependsOn chi danh dau neu chapter thuc su phu thuoc kien thuc tu chapter truoc
{chapter_hint}
{prepared_source_hint}

YEU CAU CUA GIAO VIEN:
{teacher_prompt if teacher_prompt else "(Khong co yeu cau dac biet)"}

TAI LIEU:
{markdown}

OUTPUT: CourseOutline JSON theo schema da cho. Chi tra JSON, khong giai thich."""
