export type DisplayRole = "thinking" | "tool" | "action" | "answer" | "artifact";

export type StepState = "live" | "completed";

export type PresentationMode = "compact" | "expanded" | "technical";

export type ThinkingSummaryMode = "header_only" | "body_fallback";

export interface DisplayPresentationMeta {
  displayRole?: DisplayRole;
  sequenceId?: number;
  stepId?: string;
  stepState?: StepState;
  presentation?: PresentationMode;
}

export interface ExecutionResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  images: string[];      // base64 PNG from matplotlib
  tables: unknown[][];   // pandas DataFrame as arrays
  executionTime: number;  // ms
}

export type ArtifactType = "code" | "html" | "react" | "table" | "chart" | "document" | "excel";

export interface ArtifactData {
  artifact_type: ArtifactType;
  artifact_id: string;
  title: string;
  content: string;
  language?: string;
  metadata?: {
    execution_status?: "pending" | "running" | "success" | "error";
    output?: string;
    error?: string;
    image_url?: string;
    table_data?: unknown[];
    file_url?: string;
    [key: string]: unknown;
  };
}

export interface ArtifactBlockData extends DisplayPresentationMeta {
  type: "artifact";
  id: string;
  artifact: ArtifactData;
  node?: string;
}

export type VisualType =
  | "comparison"
  | "process"
  | "matrix"
  | "architecture"
  | "concept"
  | "infographic"
  | "chart"
  | "timeline"
  | "map_lite"
  | "simulation"
  | "quiz"
  | "interactive_table"
  | "react_app";

export type VisualRuntime = "svg" | "sandbox_html" | "sandbox_react";

export type VisualRendererKind = "template" | "inline_html" | "app" | "recharts";

export type VisualShellVariant = "editorial" | "compact" | "immersive";

export type VisualPatchStrategy = "spec_merge" | "replace_html" | "app_state";

export type VisualInteractionMode = "static" | "guided" | "explorable" | "scrubbable" | "filterable";

export type VisualLifecycleEventType = "visual_open" | "visual_patch";

export type VisualSessionStatus = "open" | "committed" | "disposed";

export type VisualPedagogicalRole =
  | "problem"
  | "mechanism"
  | "comparison"
  | "architecture"
  | "result"
  | "benchmark"
  | "conclusion";

export type VisualChromeMode = "editorial" | "app" | "immersive";

export interface VisualRuntimeManifest {
  ui_runtime: string;
  storage?: boolean;
  mcp_access?: boolean;
  file_export?: boolean;
  shareability?: string;
}

export interface VisualControlOption {
  value: string;
  label: string;
}

export interface VisualControl {
  id: string;
  type: "select" | "range" | "chips" | "toggle";
  label: string;
  value?: string | number | boolean;
  min?: number;
  max?: number;
  step?: number;
  options?: VisualControlOption[];
}

export interface VisualAnnotation {
  id: string;
  title: string;
  body: string;
  target_id?: string;
  tone?: "neutral" | "accent" | "warning" | "success";
}

export interface VisualSceneNode {
  id: string;
  label: string;
  kind?: string;
  parent_id?: string;
  metadata?: Record<string, unknown>;
}

export interface VisualScenePanel {
  id: string;
  title: string;
  body?: string;
  node_ids?: string[];
}

export interface VisualScene {
  kind: string;
  nodes?: VisualSceneNode[];
  links?: Array<{
    source: string;
    target: string;
    label?: string;
  }>;
  panels?: VisualScenePanel[];
  scales?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface VisualPayload {
  id: string;
  visual_session_id: string;
  type: VisualType;
  renderer_kind: VisualRendererKind;
  shell_variant: VisualShellVariant;
  patch_strategy: VisualPatchStrategy;
  figure_group_id: string;
  figure_index: number;
  figure_total: number;
  pedagogical_role: VisualPedagogicalRole;
  chrome_mode: VisualChromeMode;
  claim: string;
  presentation_intent?: "text" | "article_figure" | "chart_runtime" | "code_studio_app" | "artifact";
  figure_budget?: number;
  quality_profile?: "draft" | "standard" | "premium";
  renderer_contract?: "host_shell" | "chart_runtime" | "article_figure";
  studio_lane?: "app" | "artifact" | "widget" | null;
  artifact_kind?: "html_app" | "code_widget" | "search_widget" | "document" | "chart_widget" | null;
  narrative_anchor: string;
  runtime: VisualRuntime;
  title: string;
  summary: string;
  spec: Record<string, unknown>;
  scene: VisualScene;
  controls: VisualControl[];
  annotations: VisualAnnotation[];
  interaction_mode: VisualInteractionMode;
  ephemeral: boolean;
  lifecycle_event: VisualLifecycleEventType;
  subtitle?: string;
  fallback_html?: string;
  runtime_manifest?: VisualRuntimeManifest | null;
  artifact_handoff_available?: boolean;
  artifact_handoff_mode?: "none" | "followup_prompt";
  artifact_handoff_label?: string | null;
  artifact_handoff_prompt?: string | null;
  metadata?: Record<string, unknown>;
}

export interface VisualBlockData extends DisplayPresentationMeta {
  type: "visual";
  id: string;
  sessionId?: string;
  visual: VisualPayload;
  node?: string;
  status?: VisualSessionStatus;
}

export interface VisualSessionState {
  sessionId: string;
  latestVisual: VisualPayload;
  status: VisualSessionStatus;
  revisionCount: number;
  node?: string;
  controlValues: Record<string, string | number | boolean>;
  focusedAnnotationId?: string;
  focusedNodeId?: string;
  interactionCount: number;
  lastUpdatedAt: number;
}
