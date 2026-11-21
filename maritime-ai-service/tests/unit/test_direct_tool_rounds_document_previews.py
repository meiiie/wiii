import asyncio
import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_uploaded_document_preview_runs_host_action_without_planner_llm():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    captured: dict[str, object] = {}

    class FakeHostPreviewTool:
        name = "host_action__authoring__preview_lesson_patch"

        def invoke(self, args):
            captured["args"] = dict(args)
            return json.dumps(
                {
                    "status": "action_requested",
                    "request_id": "host-preview-1",
                    "action": "authoring.preview_lesson_patch",
                    "params": args,
                },
                ensure_ascii=False,
            )

        async def ainvoke(self, args):
            return self.invoke(args)

    class FakeHostApplyTool:
        name = "host_action__authoring__apply_lesson_patch"

        def invoke(self, args):
            captured["apply_args"] = dict(args)
            raise AssertionError(
                "uploaded document authoring must not apply before preview approval"
            )

        async def ainvoke(self, args):
            return self.invoke(args)

    events: list[dict] = []

    async def push_event(event):
        events.append(event)

    async def fake_ainvoke_with_fallback(_llm, _messages, **_kwargs):
        raise AssertionError("uploaded document preview should not depend on planner LLM")

    async def fake_stream_direct_answer_with_fallback(*args, **kwargs):
        raise AssertionError("document preview should not use no-tool streaming path")

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*args, **kwargs):
        return None

    markdown = (
        "Sổ tay trực ca buồng lái\n"
        "Marker kiểm thử: WIII_DOC_GOAL_123\n"
        "Mục tiêu học tập 1: giải thích quy trình trực ca khi tầm nhìn hạn chế.\n"
        "Checklist nguồn trang 4: xác nhận người trực ca, kiểm tra thiết bị định vị.\n"
        "Checklist nguồn trang 5: báo thuyền trưởng, giảm tốc an toàn, ghi nhật ký.\n"
    )
    state = {
        "context": {
            "document_context": {
                "attachments": [
                    {
                        "file_name": "so-tay-truc-ca.docx",
                        "markdown": markdown,
                    }
                ]
            },
            "page_context": {"lesson_id": "lesson-from-url"},
        }
    }

    with patch(
        "app.engine.multi_agent.graph._ainvoke_with_fallback",
        new=fake_ainvoke_with_fallback,
    ), patch(
        "app.engine.multi_agent.graph._stream_direct_wait_heartbeats",
        new=fake_stream_direct_wait_heartbeats,
    ):
        llm_response, _messages, tool_call_events = await execute_direct_tool_rounds_impl(
            llm_with_tools=object(),
            llm_auto=object(),
            messages=[],
            tools=[FakeHostPreviewTool(), FakeHostApplyTool()],
            push_event=push_event,
            query=(
                "Dua tren tai lieu Word vua upload, tao preview_lesson_patch "
                "co source_references page 4-5 va marker WIII_DOC_GOAL_123."
            ),
            state=state,
            forced_tool_choice="host_action__authoring__preview_lesson_patch",
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    preview_args = captured["args"]
    assert preview_args["lesson_id"] == "lesson-from-url"
    assert preview_args["title"].startswith("Bản nháp:")
    assert "# Bản nháp bài học từ tài liệu:" in preview_args["content"]
    assert "## Mục tiêu học tập" in preview_args["content"]
    assert "## Hoạt động thảo luận" in preview_args["content"]
    assert "Marker kiểm thử: WIII_DOC_GOAL_123" in preview_args["content"]
    assert "Ban nhap" not in preview_args["content"]
    assert "Muc tieu hoc tap" not in preview_args["content"]
    assert "WIII_DOC_GOAL_123" in preview_args["content"]
    assert preview_args["source_references"][0]["page_start"] == 4
    assert preview_args["source_references"][0]["page_end"] == 5
    assert [event["type"] for event in tool_call_events] == ["call", "host_action", "result"]
    assert any(event.get("type") == "host_action" for event in events)
    assert "apply_args" not in captured
    assert "preview" in llm_response.content.lower()

def test_uploaded_doc_preview_skips_logo_data_uri_and_focuses_teacher_manual():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    markdown = (
        "![Logo Trường Đại học Hàng hải Việt Nam](data:image/png;base64...)\n\n"
        "**HƯỚNG DẪN SỬ DỤNG\n"
        "HOLILIHU ONLINE LMS**\n\n"
        "| **Vai trò** | **Nên đọc trước** | **Mục tiêu sau khi đọc** |\n"
        "| --- | --- | --- |\n"
        "| **Giảng viên** | Phần 4 và 5 | Biết tạo khóa, soạn nội dung và xuất bản. |\n\n"
        "# 4. Hướng Dẫn Cho Giảng Viên\n"
        "Mục tiêu học tập: giảng viên biết tạo khóa học, soạn bài học và kiểm tra trước khi xuất bản.\n"
        "Quy trình thao tác: mở trang quản lý khóa học, cập nhật bài học, thêm tài liệu và kiểm tra quiz.\n"
        "Checklist triển khai: xác nhận tiêu đề, nội dung, tài liệu đính kèm, trạng thái xuất bản và quyền truy cập học viên.\n"
    )
    params = _build_uploaded_doc_preview_params(
        (
            'Dựa trên tài liệu Word, tạo preview cho giáo viên. '
            'Trong preview gửi source_references title là "Hướng dẫn sử dụng HoLiLiHu LMS". '
            'Marker WIII_DOC_GOAL_REAL_MANUAL.'
        ),
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "Huong_dan_su_dung_HoLiLiHu_LMS_Chi_tiet_2026-05-10.docx",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"lesson_id": "lesson-manual"},
            }
        },
    )

    content = params["content"]
    assert params["title"] == "Bản nháp: Hướng dẫn sử dụng HoLiLiHu LMS"
    assert params["lesson_id"] == "lesson-manual"
    assert params["source_references"][0]["title"] == "Hướng dẫn sử dụng HoLiLiHu LMS"
    assert "Logo Trường Đại học Hàng hải" not in params["title"]
    assert "data:image" not in content
    assert "| **Vai trò**" not in content
    assert "## Checklist thao tác / nội dung cần nắm" in content
    assert "giảng viên biết tạo khóa học" in content
    assert "trực ca" not in content.lower()
    assert "WIII_DOC_GOAL_REAL_MANUAL" in content

def test_uploaded_doc_preview_preserves_general_wiii_marker_from_query():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    marker = "WIII_PRODUCT_E2E_20260512024500"
    params = _build_uploaded_doc_preview_params(
        (
            "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload. "
            f"Noi dung bai hoc moi phai chua marker kiem thu chinh xac: {marker}."
        ),
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "Muc tieu hoc tap: giao vien tao khoa hoc va kiem tra noi dung.\n"
                                "Quy trinh thao tac: mo khoa hoc, cap nhat bai hoc, kiem tra quiz.\n"
                            ),
                        }
                    ]
                },
                "page_context": {"lesson_id": "lesson-e2e"},
            }
        },
    )

    assert params["lesson_id"] == "lesson-e2e"
    assert marker in params["content"]

def test_uploaded_doc_preview_preserves_labelled_non_wiii_marker_from_query():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    marker = "COURSE_PATCH_MARKER_42"
    params = _build_uploaded_doc_preview_params(
        (
            "Create a safe LMS preview from the uploaded document. "
            f"Exact marker: {marker}."
        ),
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Bridge resource management guide\n"
                                "Learning objective: verify the checklist before saving.\n"
                                "Checklist: title, lesson content, source references, preview approval.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    assert marker in params["content"]

def test_uploaded_doc_preview_prefers_explicit_query_title_over_parser_metadata():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        (
            'Tao preview_lesson_patch cho giao vien. '
            'Trong preview gui source_references title la "Huong dan su dung HoLiLiHu LMS".'
        ),
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "title": "Parser provenance",
                            "markdown": (
                                "Parser provenance\n"
                                "Muc tieu hoc tap: giao vien cap nhat bai hoc trong LMS.\n"
                                "Checklist: kiem tra tieu de, noi dung va nguon truoc khi luu.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    assert params["title"] == "Bản nháp: Hướng dẫn sử dụng HoLiLiHu LMS"
    assert params["source_references"][0]["title"] == "Hướng dẫn sử dụng HoLiLiHu LMS"
    assert "# Bản nháp bài học từ tài liệu: Hướng dẫn sử dụng HoLiLiHu LMS" in params["content"]
    assert "Parser provenance" not in params["title"]

def test_uploaded_doc_preview_prefers_real_teacher_heading_over_smart_excerpt_outline():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    markdown = (
        "# Tai lieu upload: manual.docx\n\n"
        "## Muc luc phat hien\n"
        "- 3. Huong Dan Cho Hoc Vien\n"
        "- 4. Huong Dan Cho Giang Vien\n"
        "- 4.2. Tao khoa hoc moi\n\n"
        "## Trich doan dau tai lieu\n"
        "Vai tro: Hoc vien, Giang vien, Quan ly.\n\n"
        "## Trich doan uu tien theo vai tro/chu de\n"
        "### 4. Huong Dan Cho Giang Vien\n"
        "# 4. Huong Dan Cho Giang Vien\n"
        "Phan nay tap trung vao tac vu tao va van hanh khoa hoc.\n\n"
        "## 4.2. Tao khoa hoc moi\n"
        "**Giang vien**\n\n"
        "| **Muc tieu** | Nhap thong tin khoa theo cach du dung cho duyet va cho hoc vien hieu. |\n"
        "| --- | --- |\n"
        "| **Buoc** | **Thao tac** | **Ket qua dung** |\n"
        "| **1** | Bam Tao khoa hoc. | Form co cac nhom thong tin tach ro. |\n"
        "| **2** | Nhap tieu de ro rang. | Truong bat buoc bao loi neu thieu. |\n"
        "Checklist trien khai: tieu de, noi dung, video tuong tac, cau hoi va trang thai xuat ban.\n"
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien voi source_references tu tai lieu LMS nay.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": markdown,
                        }
                    ]
                }
            }
        },
    )

    content = params["content"]
    assert "Tai lieu upload" not in content
    assert "Muc luc phat hien" not in content
    assert "- 4. Huong Dan Cho Giang Vien" not in content
    assert "Nhap thong tin khoa" in content
    assert "Checklist trien khai" in content
    assert "HoLiLiHu LMS" in params["description"]
    assert "OOW" not in params["description"]

def test_doc_preview_clean_line_drops_checkbox_table_markers():
    from app.engine.multi_agent.direct_document_preview_text import _clean_doc_preview_line

    assert _clean_doc_preview_line(
        "| **□** | Thong tin khoa hoan chinh. | Co tieu de va muc tieu hoc tap. |"
    ) == "Thong tin khoa hoan chinh. - Co tieu de va muc tieu hoc tap."

def test_uploaded_doc_preview_filters_bare_table_labels_from_goals():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "| **Muc tieu** |\n"
                                "| **Muc tieu hoc tap** |\n"
                                "| **Buoc** | **Thao tac** | **Ket qua dung** |\n"
                                "Muc tieu hoc tap: giao vien cap nhat bai hoc va kiem tra nguon truoc khi luu.\n"
                                "Checklist: xac nhan tieu de, noi dung, nguon va trang thai xuat ban.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    content = params["content"]
    assert "- Muc tieu\n" not in content
    assert "- Muc tieu hoc tap\n" not in content
    assert "- Buoc" not in content
    assert "- Thao tac" not in content
    assert "giao vien cap nhat bai hoc" in content
    assert "xac nhan tieu de" in content

def test_uploaded_doc_preview_keeps_ordered_actions_out_of_learning_goals():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "Muc tieu hoc tap: giao vien hieu cach chuan bi bai hoc truoc khi luu.\n"
                                "| **Buoc** | **Thao tac** | **Ket qua dung** |\n"
                                "| **3** | Them anh dai dien va nhap muc tieu bai hoc khi soan bai. |"
                                "Noi dung duoc hien thi dung cho hoc vien. |\n"
                                "Checklist: xac nhan source references va preview approval.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    content = params["content"]
    objectives_section = content.split("## Checklist", 1)[0]
    checklist_section = content.split("## Checklist", 1)[1]
    assert "giao vien hieu cach chuan bi bai hoc" in objectives_section
    assert "Them anh dai dien" not in objectives_section
    assert "- 3 - Them anh" not in content
    assert "Them anh dai dien va nhap muc tieu bai hoc" in checklist_section

def test_uploaded_doc_preview_excludes_admonitions_from_learning_goals():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "Khong nen dan van ban qua dai mot doan. "
                                "Chia thanh muc tieu, doi tuong, yeu cau dau vao.\n"
                                "Luu y: giao vien kiem tra citation truoc khi luu.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    content = params["content"]
    objectives_section = content.split("## Checklist", 1)[0]
    assert "Khong nen dan van ban qua dai" not in objectives_section
    assert "Luu y: giao vien kiem tra citation" not in objectives_section
    assert "Giáo viên xác định đúng thao tác cần làm trong LMS" in objectives_section

def test_uploaded_doc_preview_shapes_descriptive_excerpt_into_learning_goal():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "Phan nay tap trung vao tac vu tao va van hanh khoa hoc: "
                                "lap khoa, soan noi dung, tao cau hoi va cau hinh video.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    objectives_section = params["content"].split("## Checklist", 1)[0]
    assert "Phan nay tap trung vao" not in objectives_section
    assert (
        "Giáo viên thực hiện được tac vu tao va van hanh khoa hoc"
        in objectives_section
    )

def test_uploaded_doc_preview_repairs_truncated_publish_word_in_learning_goal():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "Phan nay tap trung vao tac vu tao va van hanh khoa hoc: "
                                "lap khoa, soan noi dung, tao cau hoi, cau hinh video, "
                                "kiem tra roi xuat ba\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    objectives_section = params["content"].split("## Checklist", 1)[0]
    assert "xuat ba trong LMS" not in objectives_section
    assert "xuất bản trong LMS" in objectives_section

def test_uploaded_doc_preview_supplements_sparse_lms_learning_goals():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_preview_params,
    )

    params = _build_uploaded_doc_preview_params(
        "Tao preview_lesson_patch cho giao vien tu tai lieu vua upload.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "manual.docx",
                            "markdown": (
                                "Huong dan su dung HoLiLiHu LMS\n"
                                "Muc tieu hoc tap: giao vien tao khoa hoc dung quy trinh.\n"
                            ),
                        }
                    ]
                }
            }
        },
    )

    objectives_section = params["content"].split("## Checklist", 1)[0]
    objective_lines = [
        line for line in objectives_section.splitlines() if line.startswith("- ")
    ]
    assert len(objective_lines) >= 3
    assert "giao vien tao khoa hoc dung quy trinh" in objectives_section
    assert "phần so sánh thay đổi và nguồn trích dẫn" in objectives_section
    assert "diff, citation" not in objectives_section
    assert "bấm Apply" not in objectives_section
    assert "trạng thái nháp" in objectives_section
