import json


class TestToolGenerateVisual:
    """Test the structured visual payload tool."""

    def test_returns_visual_payload_json(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "left": {"title": "Softmax"},
                "right": {"title": "Linear"},
            }),
            "title": "Softmax vs Linear",
            "summary": "Quick comparison",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.type == "comparison"
        assert payload.renderer_kind == "inline_html"
        assert payload.shell_variant == "editorial"
        assert payload.patch_strategy == "replace_html"
        assert payload.runtime == "sandbox_html"
        assert payload.title == "Softmax vs Linear"
        assert payload.summary == "Quick comparison"
        assert payload.visual_session_id.startswith("vs-comparison-")
        assert payload.figure_group_id.startswith("fg-comparison-")
        assert payload.figure_index == 1
        assert payload.figure_total == 1
        assert payload.pedagogical_role == "comparison"
        assert payload.chrome_mode == "editorial"
        assert payload.claim == "Quick comparison"
        assert payload.scene["kind"] == "comparison"
        assert payload.scene["render_surface"] == "html"
        assert payload.scene["state_model"]["kind"] == "semantic_svg_scene"
        assert payload.controls[0]["id"] == "focus_side"
        assert payload.annotations
        assert payload.lifecycle_event == "visual_open"
        assert payload.fallback_html is not None
        assert payload.metadata["source_tool"] == "tool_generate_visual"

    def test_returns_grouped_figure_payloads_for_article_flow(self):
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "figures": [
                    {
                        "type": "comparison",
                        "title": "Chi phi tinh toan",
                        "summary": "Softmax tang nhanh hon khi context dai ra.",
                        "claim": "Figure 1 chot van de chi phi tinh toan.",
                        "pedagogical_role": "problem",
                        "spec": {
                            "left": {"title": "Softmax attention"},
                            "right": {"title": "Linear attention"},
                        },
                    },
                    {
                        "type": "process",
                        "title": "Co che cap nhat bo nho",
                        "pedagogical_role": "mechanism",
                        "spec": {
                            "steps": [
                                {"title": "Doc token moi"},
                                {"title": "Cap nhat state S"},
                                {"title": "Sinh dau ra"},
                            ],
                        },
                    },
                ],
            }),
            "title": "Giai thich Kimi Linear",
        })
        payloads = parse_visual_payloads(result)

        assert len(payloads) == 2
        assert {payload.figure_index for payload in payloads} == {1, 2}
        assert {payload.figure_total for payload in payloads} == {2}
        assert len({payload.figure_group_id for payload in payloads}) == 1
        assert payloads[0].pedagogical_role == "problem"
        assert payloads[1].pedagogical_role == "mechanism"
        assert payloads[0].claim == "Figure 1 chot van de chi phi tinh toan."
        assert payloads[1].claim
        assert payloads[0].renderer_kind == "template"
        assert payloads[1].renderer_kind == "template"
        assert payloads[0].metadata["source_tool"] == "tool_generate_visual"
        assert payloads[1].metadata["source_tool"] == "tool_generate_visual"

    def test_supports_patch_operation_with_existing_session(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "process",
            "spec_json": json.dumps({
                "steps": [{"title": "Step 1"}, {"title": "Step 2"}],
            }),
            "visual_session_id": "vs-process-123",
            "operation": "patch",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.visual_session_id == "vs-process-123"
        assert payload.lifecycle_event == "visual_patch"
        assert payload.patch_strategy == "replace_html"
        assert payload.scene["kind"] == "process"

    def test_runtime_context_can_promote_followup_to_patch(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-comparison-keep",
            },
        )
        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "comparison",
                "spec_json": json.dumps({
                    "left": {"title": "Before"},
                    "right": {"title": "After"},
                }),
                "operation": "open",
            })

        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.visual_session_id == "vs-comparison-keep"
        assert payload.lifecycle_event == "visual_patch"

    def test_runtime_context_overrides_hallucinated_patch_session_id(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-comparison-keep",
            },
        )
        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "process",
                "spec_json": json.dumps({
                    "steps": [{"title": "One"}, {"title": "Two"}, {"title": "Three"}],
                }),
                "operation": "patch",
                "visual_session_id": "hallucinated-new-session",
            })

        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.visual_session_id == "vs-comparison-keep"
        assert payload.lifecycle_event == "visual_patch"

    def test_rejects_removed_legacy_sandbox_types(self):
        from app.engine.tools.visual_tools import tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "simulation",
            "spec_json": json.dumps({
                "html": "<div>Sim</div>",
                "ui_runtime": "html",
            }),
        })
        assert "Error" in result
        assert "simulation" in result

    def test_supports_inline_html_renderer(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "concept",
            "spec_json": json.dumps({
                "html": "<section><h1>Custom inline visual</h1></section>",
            }),
            "renderer_kind": "inline_html",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        assert payload.patch_strategy == "replace_html"
        assert payload.fallback_html is not None

    def test_runtime_context_prefers_inline_html_for_chart_runtime_when_llm_codegen_enabled(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())

        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-chart-inline-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "inline_html",
                "visual_intent_reason": "chart-runtime",
                "presentation_intent": "chart_runtime",
                "visual_user_query": "Ve bieu do so sanh toc do cac loai tau container",
                "visual_requested_type": "chart",
                "preferred_render_surface": "svg",
                "planning_profile": "chart_svg",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({
                    "chart_type": "bar",
                    "labels": ["Feeder", "Panamax", "Neo-Panamax"],
                    "datasets": [
                        {"label": "Speed", "data": [18, 22, 24]},
                    ],
                }),
                "title": "Toc do tau container",
                "summary": "So sanh toc do danh nghia giua cac nhom tau container.",
            })

        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        assert payload.patch_strategy == "replace_html"
        assert payload.runtime == "sandbox_html"
        assert payload.scene["render_surface"] == "svg"
        assert payload.fallback_html is not None
        assert payload.artifact_handoff_available is True
        assert payload.artifact_handoff_mode == "followup_prompt"
        assert payload.artifact_handoff_label == "Mo thanh Artifact"
        assert payload.artifact_handoff_prompt is not None
        assert "artifact" in payload.artifact_handoff_prompt.lower()

    def test_runtime_context_auto_groups_explanatory_template_visuals(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "chart-template",
                "visual_user_query": "Explain Kimi linear attention in charts",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({
                    "chart_type": "line",
                    "labels": ["1k", "4k", "16k", "64k"],
                    "datasets": [
                        {"label": "Softmax", "data": [1, 16, 256, 4096]},
                        {"label": "Linear", "data": [1, 4, 16, 64]},
                    ],
                }),
                "title": "Compute cost vs context length",
                "summary": "Softmax tang nhanh hon Linear khi context dai len.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 2
        assert payloads[0].figure_total == 2
        assert payloads[1].figure_total == 2
        assert payloads[0].type == "chart"
        assert payloads[1].type == "infographic"
        assert payloads[0].renderer_kind == "template"
        assert payloads[1].renderer_kind == "template"
        assert payloads[0].pedagogical_role == "benchmark"
        assert payloads[1].pedagogical_role == "conclusion"

    def test_runtime_context_can_plan_three_figures_for_dense_stepwise_explanation(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-3",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "chart-template",
                "visual_user_query": "Explain Kimi linear attention in charts step by step with mechanism and benchmark",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({
                    "chart_type": "line",
                    "labels": ["1k", "4k", "16k", "64k", "256k", "1M"],
                    "datasets": [
                        {"label": "Softmax", "data": [1, 16, 256, 4096, 65536, 1048576]},
                        {"label": "Linear", "data": [1, 4, 16, 64, 256, 1024]},
                    ],
                }),
                "title": "Compute cost vs context length",
                "summary": "Softmax tang nhanh hon Linear khi context dai len.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 3
        assert [payload.figure_total for payload in payloads] == [3, 3, 3]
        assert [payload.type for payload in payloads] == ["chart", "infographic", "infographic"]
        assert all(payload.renderer_kind == "template" for payload in payloads)
        assert [payload.pedagogical_role for payload in payloads] == ["benchmark", "mechanism", "conclusion"]

    def test_runtime_context_keeps_simple_template_visual_single_when_scope_is_narrow(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-simple-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "comparison",
                "visual_user_query": "So sanh nhanh TCP va UDP",
                "visual_requested_type": "comparison",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "comparison",
                "spec_json": json.dumps({
                    "left": {"title": "TCP"},
                    "right": {"title": "UDP"},
                }),
                "title": "TCP vs UDP",
                "summary": "Dat TCP canh UDP de thay su khac nhau co ban.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 1
        assert payloads[0].figure_total == 1
        assert payloads[0].type == "comparison"

    def test_runtime_context_rejects_removed_legacy_type_in_app_mode(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-app-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "app",
                "visual_intent_reason": "app-request",
                "visual_user_query": "Hay mo phong vat ly con lac",
                "visual_requested_type": "simulation",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "simulation",
                "spec_json": json.dumps({
                    "html": "<div>Sim</div>",
                    "ui_runtime": "html",
                }),
            })

        assert "Error" in result
        assert "simulation" in result

    def test_runtime_context_auto_groups_infographic_explanations(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-infographic-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "article-figure",
                "visual_user_query": "Explain Kimi linear attention in charts",
                "visual_requested_type": "infographic",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "infographic",
                "spec_json": json.dumps({
                    "sections": [
                        {"title": "Van de", "content": "Softmax can ma tran day du O(n^2)."},
                        {"title": "Co che", "content": "Linear attention chuyen sang running state."},
                        {"title": "Ket qua", "content": "Context dai hon voi chi phi gon hon."},
                    ],
                }),
                "title": "Co che Linear Attention cua Kimi",
                "summary": "Ba diem nhan: van de, co che, va ket qua.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 2
        assert payloads[0].figure_total == 2
        assert payloads[1].figure_total == 2
        assert payloads[0].type == "infographic"
        assert payloads[1].type == "infographic"
        assert payloads[0].renderer_kind == "template"
        assert payloads[1].renderer_kind == "template"

    def test_runtime_context_does_not_auto_group_patch_turn(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-patch-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "comparison",
                "visual_user_query": "Giu visual hien tai va highlight bottleneck",
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-comparison-keep",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "comparison",
                "spec_json": json.dumps({
                    "left": {"title": "Before"},
                    "right": {"title": "After"},
                }),
                "operation": "open",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 1
        assert payloads[0].lifecycle_event == "visual_patch"
        assert payloads[0].visual_session_id == "vs-comparison-keep"

    def test_generates_natural_default_summary_and_takeaway_annotation(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "left": {"title": "Softmax attention"},
                "right": {"title": "Linear attention"},
            }),
            "title": "Softmax vs Linear",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.summary == "Đặt Softmax attention cạnh Linear attention để thấy điểm khác biệt chính."
        assert payload.annotations[0]["title"] == "Điểm chốt"
