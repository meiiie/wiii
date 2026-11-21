import asyncio
import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_uploaded_document_course_plan_runs_host_action_without_planner_llm():
    from app.engine.multi_agent.direct_tool_rounds_runtime import (
        execute_direct_tool_rounds_impl,
    )

    captured: dict[str, object] = {}

    class FakeHostCourseTool:
        name = "host_action__authoring__generate_course_from_document"

        def invoke(self, args):
            captured["args"] = dict(args)
            return json.dumps(
                {
                    "status": "action_requested",
                    "request_id": "host-course-1",
                    "action": "authoring.generate_course_from_document",
                    "params": args,
                },
                ensure_ascii=False,
            )

        async def ainvoke(self, args):
            return self.invoke(args)

    events: list[dict] = []

    async def push_event(event):
        events.append(event)

    async def fake_ainvoke_with_fallback(_llm, _messages, **_kwargs):
        raise AssertionError("uploaded document course plan should not depend on planner LLM")

    async def fake_stream_direct_answer_with_fallback(*args, **kwargs):
        raise AssertionError("document course plan should not use no-tool streaming path")

    async def fake_stream_direct_wait_heartbeats(*args, **kwargs):
        stop_signal = kwargs.get("stop_signal")
        if stop_signal is not None:
            await stop_signal.wait()
            return
        await asyncio.Future()

    async def push_status_only_progress(*args, **kwargs):
        return None

    markdown = (
        "# Hướng Dẫn Sử Dụng HoLiLiHu LMS\n"
        "Nguồn section: 1. Tổng Quan (trang 1-2)\n"
        "# 3. Hướng Dẫn Cho Học Viên\n"
        "Nguồn section: 3. Hướng Dẫn Cho Học Viên (trang 12-20)\n"
        "# 4. Hướng Dẫn Cho Giảng Viên\n"
        "Nguồn section: 4. Hướng Dẫn Cho Giảng Viên (trang 21-34)\n"
        "## 4.2. Tạo khóa học mới\n"
        "Nguồn section: 4.2. Tạo khóa học mới (trang 23-25)\n"
        "## 4.5. Thêm video, tài liệu và quiz\n"
        "Nguồn section: 4.5. Thêm video, tài liệu và quiz (trang 29-31)\n"
        "# 5. Hướng Dẫn Cho Quản Lý\n"
        "Nguồn section: 5. Hướng Dẫn Cho Quản Lý (trang 35-42)\n"
    )
    state = {
        "context": {
            "document_context": {
                "attachments": [
                    {
                        "file_name": "Huong_dan_su_dung_HoLiLiHu_LMS.docx",
                        "markdown": markdown,
                    }
                ]
            },
            "page_context": {"course_id": "course-from-url"},
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
            tools=[FakeHostCourseTool()],
            push_event=push_event,
            query="Dựa trên tài liệu Word vừa upload, hãy tạo toàn bộ khóa học theo chương/bài có citation.",
            state=state,
            forced_tool_choice="host_action__authoring__generate_course_from_document",
            ainvoke_with_fallback=fake_ainvoke_with_fallback,
            stream_direct_answer_with_fallback=fake_stream_direct_answer_with_fallback,
            stream_direct_wait_heartbeats=fake_stream_direct_wait_heartbeats,
            push_status_only_progress=push_status_only_progress,
        )

    course_args = captured["args"]
    course_plan = course_args["course_plan"]
    assert course_args["course_id"] == "course-from-url"
    assert course_args["action"] == "preview_course_plan_from_document"
    assert course_plan["title"] == "Khai thác HoLiLiHu LMS từ tài liệu hướng dẫn"
    assert len(course_plan["chapters"]) == 5
    assert sum(len(chapter["lessons"]) for chapter in course_plan["chapters"]) >= 15
    assert "Tác nghiệp giảng viên" in course_plan["chapters"][2]["title"]
    assert "source_references" in course_plan["chapters"][2]["lessons"][0]
    assert any(ref.get("page_start") == 23 for ref in course_args["source_references"])
    assert [event["type"] for event in tool_call_events] == ["call", "host_action", "result"]
    assert any(event.get("type") == "host_action" for event in events)
    assert "khóa học" in llm_response.content.lower()

def test_uploaded_doc_course_plan_builder_creates_full_lms_architecture():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
    )

    markdown = (
        "# Hướng Dẫn Sử Dụng HoLiLiHu LMS\n"
        "Nguồn section: 1. Tổng Quan (trang 1-2)\n"
        "# 3. Hướng Dẫn Cho Học Viên\n"
        "Nguồn section: 3. Hướng Dẫn Cho Học Viên (trang 12-20)\n"
        "# 4. Hướng Dẫn Cho Giảng Viên\n"
        "Nguồn section: 4. Hướng Dẫn Cho Giảng Viên (trang 21-34)\n"
        "## 4.2. Tạo khóa học mới\n"
        "Nguồn section: 4.2. Tạo khóa học mới (trang 23-25)\n"
        "## 4.5. Thêm video, tài liệu và quiz\n"
        "Nguồn section: 4.5. Thêm video, tài liệu và quiz (trang 29-31)\n"
        "# 5. Hướng Dẫn Cho Quản Lý\n"
        "Nguồn section: 5. Hướng Dẫn Cho Quản Lý (trang 35-42)\n"
    )
    params = _build_uploaded_doc_course_params(
        "Tạo khóa học đầy đủ từ tài liệu Word này, chia chương/bài có source_references.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "Huong_dan_su_dung_HoLiLiHu_LMS.docx",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"course_id": "course-1"},
            }
        },
    )

    plan = params["course_plan"]
    assert params["course_id"] == "course-1"
    assert params["changed_fields"] == ["course_structure"]
    assert params["summary"].endswith("tài liệu upload.")
    assert "trích dẫn" not in params["summary"]
    assert "LMS" not in params["summary"]
    assert len(plan["chapters"]) == 5
    titles = [chapter["title"] for chapter in plan["chapters"]]
    assert any("Hành trình học viên" in title for title in titles)
    assert any("Tác nghiệp giảng viên" in title for title in titles)
    assert any("Quản lý" in title for title in titles)
    assert plan["chapters"][2]["lessons"][0]["source_references"][0]["page_start"] == 23
    assert f"{sum(len(chapter['lessons']) for chapter in plan['chapters'])} bài" in plan["duration"]
    assert "không publish tự động" in " ".join(plan["implementation_checklist"])

def test_uploaded_doc_course_plan_builder_keeps_maritime_research_out_of_lms_manual():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
        _normalize_doc_preview_text,
    )

    markdown = (
        "# NGHIEN CUU XAY DUNG HE THONG QUAN LY VAN HANH VA HO SO TAU THUY\n"
        "Nguon section: GIOI THIEU (trang 1-4)\n"
        "# GIOI THIEU\n"
        "Gioi thieu bai toan xay dung he thong quan ly van hanh va ho so tau thuy.\n"
        "Nguon section: Gioi thieu bai toan xay dung he thong quan ly van hanh va ho so tau thuy (trang 5-8)\n"
        "# KHAO SAT BAI TOAN VAN HANH VA HO SO TAU THUY\n"
        "Nguon section: Khao sat bai toan van hanh va ho so tau thuy (trang 9-20)\n"
        "## Nghiep vu quan ly van hanh va ho so tau thuy\n"
        "Nguon section: Nghiep vu quan ly van hanh va ho so tau thuy (trang 18-28)\n"
        "# PHAN TICH VA THIET KE HE THONG\n"
        "Nguon section: Phan tich va thiet ke he thong (trang 29-40)\n"
        "## Phan tich chuc nang cua he thong tau\n"
        "Nguon section: Phan tich chuc nang cua he thong tau (trang 41-50)\n"
        "## So do luong du lieu muc ngu canh\n"
        "Nguon section: So do luong du lieu muc ngu canh (trang 51-60)\n"
        "## Thiet ke co so du lieu tau\n"
        "Nguon section: Thiet ke co so du lieu tau (trang 61-80)\n"
        "## Cac bang du lieu\n"
        "Nguon section: Cac bang du lieu (trang 81-95)\n"
        "## Phan tich chuc nang cua he thong bo\n"
        "Nguon section: Phan tich chuc nang cua he thong bo (trang 96-110)\n"
        "# KET LUAN VA HUONG PHAT TRIEN\n"
        "Nguon section: Ket luan va huong phat trien (trang 111-120)\n"
    )
    params = _build_uploaded_doc_course_params(
        (
            "Lap chuong trinh dao tao cho giao vien tu tai lieu Word nay. "
            "Khong bien thanh huong dan HoLiLiHu LMS; hay bam vao van hanh, "
            "ho so tau thuy va doanh nghiep van tai bien."
        ),
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "40 - GV.25-26.01.31 - Nghien cuu he thong quan ly van hanh va ho so tau thuy.docx",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"course_id": "course-vessel"},
            }
        },
    )

    plan = params["course_plan"]
    normalized_plan = _normalize_doc_preview_text(json.dumps(plan, ensure_ascii=False))
    assert params["course_id"] == "course-vessel"
    assert len(plan["chapters"]) == 6
    assert sum(len(chapter["lessons"]) for chapter in plan["chapters"]) == 18
    assert "holilihu" not in normalized_plan
    assert "dang nhap" not in normalized_plan
    assert "video tuong tac" not in normalized_plan
    assert "ho so tau" in normalized_plan
    assert "van tai bien" in normalized_plan
    assert "co so du lieu" in normalized_plan or "du lieu" in normalized_plan
    assert all(
        lesson.get("source_references")
        for chapter in plan["chapters"]
        for lesson in chapter["lessons"]
    )

def test_uploaded_doc_course_plan_builder_keeps_maritime_lms_research_out_of_holilihu_manual():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
        _normalize_doc_preview_text,
    )

    markdown = (
        "CONG TRINH\n\n"
        "**NGHIEN CUU XAY DUNG HE THONG LMS NANG CAO NGHIEP VU CHUYEN MON CHO CAC THUY THU**\n"
        "# GIOI THIEU\n"
        "Tai lieu phan tich nhu cau boi duong nghiep vu chuyen mon cho thuy thu bang he thong LMS.\n"
        "Nguon section: Gioi thieu nhu cau dao tao thuy thu (trang 1-5)\n"
        "# CO SO LY LUAN VA THUC TIEN\n"
        "Trinh bay co so e-learning, quan ly hoc tap va dac thu dao tao hang hai.\n"
        "Nguon section: Co so ly luan va thuc tien (trang 6-18)\n"
        "# PHAN TICH VA THIET KE HE THONG LMS\n"
        "Mo ta cac chuc nang quan ly khoa hoc, nguoi hoc, bai giang va danh gia nang luc.\n"
        "Nguon section: Phan tich va thiet ke he thong LMS (trang 19-36)\n"
        "# THU NGHIEM VA DANH GIA\n"
        "Danh gia kha nang ung dung he thong trong dao tao nghiep vu chuyen mon cho thuy thu.\n"
        "Nguon section: Thu nghiem va danh gia (trang 37-48)\n"
    )

    params = _build_uploaded_doc_course_params(
        "Tao bai giang di.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "SV25-26.43_KH-KT.docx",
                            "title": "tmpg98c_ocp",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"course_id": "course-maritime-lms"},
            }
        },
    )

    plan = params["course_plan"]
    normalized_plan = _normalize_doc_preview_text(json.dumps(plan, ensure_ascii=False))
    assert params["course_id"] == "course-maritime-lms"
    assert plan["document_domain"]["id"] == "maritime_training_lms"
    assert "holilihu" not in normalized_plan
    assert "khai thac holilihu lms" not in normalized_plan
    assert "quan ly van hanh va ho so tau" not in normalized_plan
    assert "nghien cuu xay dung he thong lms" in _normalize_doc_preview_text(
        plan["source_document_title"]
    )
    assert "nghiep vu" in normalized_plan
    assert "thuy thu" in normalized_plan

def test_uploaded_doc_course_plan_research_title_overrides_manual_markers_in_body():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
        _normalize_doc_preview_text,
    )

    markdown = (
        "CONG TRINH\n\n"
        "**NGHIEN CUU XAY DUNG HE THONG LMS NANG CAO NGHIEP VU CHUYEN MON CHO CAC THUY THU**\n"
        "# GIOI THIEU\n"
        "Tai lieu phan tich nhu cau boi duong nghiep vu chuyen mon cho thuy thu bang he thong LMS.\n"
        "Nguon section: Gioi thieu nhu cau dao tao thuy thu (trang 1-5)\n"
        "# HUONG DAN SU DUNG HE THONG LMS\n"
        "Noi dung minh hoa co cac marker dang nhap, tao khoa hoc, them video va quiz.\n"
        "HoLiLiHu LMS duoc nhac den nhu mot vi du san pham trong qua trinh nghien cuu.\n"
        "Nguon section: Phan tich chuc nang LMS va quy trinh su dung (trang 19-36)\n"
        "# THU NGHIEM VA DANH GIA\n"
        "Danh gia kha nang ung dung he thong trong dao tao nghiep vu chuyen mon cho thuy thu.\n"
        "Nguon section: Thu nghiem va danh gia (trang 37-48)\n"
    )

    params = _build_uploaded_doc_course_params(
        "Tao bai giang di.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "SV25-26.43_KH-KT.docx",
                            "title": "tmpg98c_ocp",
                            "markdown": markdown,
                        }
                    ]
                },
                "host_context": {
                    "page": {
                        "metadata": {
                            "course_id": "course-from-nested-host-metadata",
                        }
                    }
                },
            }
        },
    )

    plan = params["course_plan"]
    normalized_title = _normalize_doc_preview_text(plan["title"])
    assert params["course_id"] == "course-from-nested-host-metadata"
    assert plan["document_domain"]["id"] == "maritime_training_lms"
    assert "khai thac holilihu lms" not in normalized_title

def test_uploaded_doc_course_plan_maritime_lms_does_not_use_vessel_template():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
        _normalize_doc_preview_text,
    )

    markdown = (
        "CONG TRINH\n\n"
        "**NGHIEN CUU XAY DUNG HE THONG LMS NANG CAO NGHIEP VU CHUYEN MON CHO CAC THUY THU**\n"
        "| Sinh vien thuc hien chinh | PHAM THI MINH HONG |\n"
        "| Sinh vien thuc hien | NGUYEN THUY LINH |\n"
        "2. San pham cong nghe\n"
        "He thong LMS ho tro dao tao truc tuyen cho thuy thu va hoc vien hang hai.\n"
        "San pham duoc dinh huong phuc vu boi duong nghiep vu chuyen mon, theo doi tien do, "
        "quan ly bai giang, quiz va danh gia nang luc trong moi truong van tai bien.\n"
        "Noi dung co nhac den tau thuy va boi canh hang hai nhung trong tam la he thong LMS dao tao.\n"
        "Nguon section: 2. San pham cong nghe (trang 1-4)\n"
    )

    params = _build_uploaded_doc_course_params(
        "Tao bai giang di. Chia thanh chuong/bai co nguon trich dan.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "SV25-26.43_KH-KT.docx",
                            "title": "tmpqd4k3n0b",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"course_id": "course-prod-like-maritime-lms"},
            }
        },
    )

    plan = params["course_plan"]
    normalized_plan = _normalize_doc_preview_text(json.dumps(plan, ensure_ascii=False))
    assert params["course_id"] == "course-prod-like-maritime-lms"
    assert plan["document_domain"]["id"] == "maritime_training_lms"
    assert "nghien cuu xay dung he thong lms" in _normalize_doc_preview_text(
        plan["source_document_title"]
    )
    assert "lms nang cao nghiep vu" in normalized_plan
    assert "thuy thu" in normalized_plan
    assert "quan ly van hanh va ho so tau" not in normalized_plan
    assert "doanh nghiep van tai bien" not in normalized_plan
    assert all(
        lesson.get("source_references")
        for chapter in plan["chapters"]
        for lesson in chapter["lessons"]
    )

def test_uploaded_doc_course_title_skips_cover_metadata_for_long_thesis_doc():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
        _normalize_doc_preview_text,
    )

    title = (
        "NGHIEN CUU XAY DUNG HE THONG QUAN LY VAN HANH VA HO SO TAU THUY "
        "PHUC VU DOANH NGHIEP VAN TAI BIEN"
    )
    markdown = (
        "| BO XAY DUNG | BO GIAO DUC VA DAO TAO |\n"
        "|-------------|-------------------------|\n\n"
        "**TRUONG DAI HOC HANG HAI VIET NAM**\n\n"
        "<!-- image -->\n\n"
        "**VU DUC TINH - 97658 - CNT63CL**\n\n"
        "**BUI TRUNG HIEU - 95457 - CNT63CL**\n\n"
        "**THUC TAP TOT NGHIEP**\n\n"
        f"**{title}**\n\n"
        "HAI PHONG - 2026\n\n"
        "# MO DAU\n"
        "Tai lieu trinh bay bai toan quan ly van hanh, ho so tau thuy va doanh nghiep van tai bien.\n"
        "Nguon section: Mo dau bai toan quan ly ho so tau (trang 1-4)\n"
        "# PHAN TICH HE THONG\n"
        "Mo ta chuc nang quan ly tau, ho so, thuyen vien, bao tri va van hanh.\n"
        "Nguon section: Phan tich he thong quan ly tau (trang 5-20)\n"
    )

    params = _build_uploaded_doc_course_params(
        "Tao bai giang di.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "40 - GV.25-26.01.31.docx",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"course_id": "course-thesis"},
            }
        },
    )

    plan = params["course_plan"]
    normalized_source = _normalize_doc_preview_text(plan["source_document_title"])
    assert params["course_id"] == "course-thesis"
    assert plan["document_domain"]["id"] == "maritime_vessel_management"
    assert "bo xay dung" not in normalized_source
    assert "truong dai hoc" not in normalized_source
    assert "nghien cuu xay dung he thong quan ly van hanh" in normalized_source
    assert "doanh nghiep van tai bien" in normalized_source

def test_generic_uploaded_doc_course_clusters_full_long_document_map():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
        _normalize_doc_preview_text,
    )

    sections = []
    for index in range(1, 25):
        sections.append(
            "\n".join(
                [
                    f"# Section {index}: Operational capability {index}",
                    f"This section explains capability {index}, constraints, evidence, and practical decisions.",
                    f"Nguon section: Section {index}: Operational capability {index} (trang {index}-{index})",
                ]
            )
        )
    markdown = "# Complex operations handbook\n" + "\n\n".join(sections)

    params = _build_uploaded_doc_course_params(
        "Turn this uploaded handbook into a complete course plan with citations.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "complex-operations-handbook.docx",
                            "title": "Complex operations handbook",
                            "markdown": markdown,
                        }
                    ]
                },
                "page_context": {"course_id": "course-generic"},
            }
        },
    )

    plan = params["course_plan"]
    normalized_plan = _normalize_doc_preview_text(json.dumps(plan, ensure_ascii=False))

    assert params["course_id"] == "course-generic"
    assert plan["document_domain"]["id"] == "generic_document_course"
    assert len(plan["chapters"]) == 6
    assert sum(len(chapter["lessons"]) for chapter in plan["chapters"]) == 18
    assert plan["document_map_summary"]["strategy"] == "cluster_full_document_map"
    assert plan["document_map_summary"]["candidate_section_count"] >= 24
    assert params["quality_report"]["status"] == "pass"
    assert params["quality_report"]["source_reference_count"] >= 24
    assert "section 24" in normalized_plan
    assert "section 1" in normalized_plan
    assert all(
        lesson.get("source_references")
        for chapter in plan["chapters"]
        for lesson in chapter["lessons"]
    )

def test_uploaded_doc_course_parses_unicode_vietnamese_source_lines():
    from app.engine.multi_agent.direct_document_preview_payloads import (
        _build_uploaded_doc_course_params,
    )

    markdown = (
        "# Báo cáo vận hành\n"
        "Nguồn section: Tổng quan vận hành (trang 7-9)\n"
        "# Quy trình kiểm tra\n"
        "Nguồn section: Quy trình kiểm tra (trang 12)\n"
        "# Đánh giá sau triển khai\n"
        "Nguồn section: Đánh giá sau triển khai (trang 18-20)\n"
    )

    params = _build_uploaded_doc_course_params(
        "Tạo khóa học từ báo cáo này với citation.",
        {
            "context": {
                "document_context": {
                    "attachments": [
                        {
                            "file_name": "bao-cao-van-hanh.docx",
                            "title": "Báo cáo vận hành",
                            "markdown": markdown,
                        }
                    ]
                },
            }
        },
    )

    assert params["quality_report"]["source_reference_count"] == 3
    assert params["source_references"][0]["page_start"] == 7
    assert params["source_references"][0]["page_end"] == 9

def test_uploaded_doc_course_request_matches_real_teacher_curriculum_wording():
    from app.engine.multi_agent.document_preview_contract import (
        looks_uploaded_document_course_request as _looks_uploaded_doc_course_request,
    )

    assert _looks_uploaded_doc_course_request("Tạo bài giảng đi.")
    assert _looks_uploaded_doc_course_request("Soạn giáo án từ tài liệu vừa upload.")
    assert _looks_uploaded_doc_course_request(
        "Tu file Word vua upload, lap chuong trinh dao tao hoan chinh, "
        "de cuong khoa, lo trinh hoc va chia thanh chuong/bai co citation."
    )
    assert _looks_uploaded_doc_course_request(
        "Hay bien tai lieu nay thanh curriculum/syllabus gom nhieu chuong "
        "va nhieu bai hoc cho giao vien."
    )
