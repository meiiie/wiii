from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VisualPayloadV1(BaseModel):
    """Structured inline visual contract for streaming-first rendering."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    visual_session_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    renderer_kind: Literal["template", "inline_html", "app", "recharts"] = "template"
    shell_variant: Literal["editorial", "compact", "immersive"] = "editorial"
    patch_strategy: Literal["spec_merge", "replace_html", "app_state"] = "spec_merge"
    figure_group_id: str = Field(min_length=1)
    figure_index: int = Field(ge=1, default=1)
    figure_total: int = Field(ge=1, default=1)
    pedagogical_role: Literal[
        "problem",
        "mechanism",
        "comparison",
        "architecture",
        "result",
        "benchmark",
        "conclusion",
    ] = "mechanism"
    chrome_mode: Literal["editorial", "app", "immersive"] = "editorial"
    claim: str = Field(min_length=1)
    presentation_intent: Literal["text", "article_figure", "chart_runtime", "code_studio_app", "artifact"] = (
        "article_figure"
    )
    figure_budget: int = Field(ge=1, le=3, default=1)
    quality_profile: Literal["draft", "standard", "premium"] = "standard"
    renderer_contract: Literal["host_shell", "chart_runtime", "article_figure"] = "article_figure"
    studio_lane: Literal["app", "artifact", "widget"] | None = None
    artifact_kind: Literal["html_app", "code_widget", "search_widget", "document", "chart_widget"] | None = None
    narrative_anchor: str = "after-lead"
    runtime: Literal["svg", "sandbox_html", "sandbox_react"]
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    spec: dict[str, Any]
    scene: dict[str, Any] = Field(default_factory=dict)
    controls: list[dict[str, Any]] = Field(default_factory=list)
    annotations: list[dict[str, Any]] = Field(default_factory=list)
    interaction_mode: Literal["static", "guided", "explorable", "scrubbable", "filterable"] = "guided"
    ephemeral: bool = True
    lifecycle_event: Literal["visual_open", "visual_patch"] = "visual_open"
    subtitle: str | None = None
    fallback_html: str | None = None
    runtime_manifest: dict[str, Any] | None = None
    artifact_handoff_available: bool = False
    artifact_handoff_mode: Literal["none", "followup_prompt"] = "none"
    artifact_handoff_label: str | None = None
    artifact_handoff_prompt: str | None = None
    metadata: dict[str, Any] | None = None
