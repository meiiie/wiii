import type { UserRole } from "./identity";
import type { WiiiConnectRuntimeSnapshot } from "./runtime-diagnostics";
import type { DisplayRole, StepState, PresentationMode } from "./artifacts";

export interface ImageInput {
  type: "base64" | "url";
  media_type: string;
  data: string;
  detail?: "auto" | "low" | "high";
}

export interface ChatDocumentAttachment {
  id?: string;
  file_name: string;
  mime_type?: string | null;
  media_kind?: "document" | "video";
  size_bytes: number;
  parser?: string;
  parser_chain?: string[];
  parser_warning?: string | null;
  provenance_level?: "text_only" | "structured_text" | "page_marker" | "page_layout";
  char_count?: number;
  truncated?: boolean;
  extracted_image_count?: number;
  embedded_asset_count?: number;
  figure_count?: number;
  table_count?: number;
}

export interface ChatDocumentContextAttachment extends ChatDocumentAttachment {
  markdown: string;
}

export interface ChatDocumentContext {
  source: "desktop_upload";
  attachments: ChatDocumentContextAttachment[];
}

export interface ChatVisualContext {
  last_visual_session_id?: string;
  last_visual_type?: string;
  last_visual_title?: string;
  visual_state_summary?: string;
  active_inline_visuals?: Array<{
    visual_session_id: string;
    type: string;
    title: string;
    renderer_kind?: string;
    shell_variant?: string;
    patch_strategy?: string;
    state_summary?: string;
    summary?: string;
    status?: string;
  }>;
}

export interface WidgetFeedbackItem {
  widget_id: string;
  widget_kind: string;
  summary?: string;
  status?: string;
  title?: string;
  visual_session_id?: string;
  score?: number;
  correct_count?: number;
  total_count?: number;
  source?: string;
  data?: Record<string, unknown>;
  payload?: Record<string, unknown>;
  session_id?: string;
  message_id?: string;
  version?: string;
  timestamp: string;
}

export interface ChatWidgetFeedbackContext {
  last_widget_kind?: string;
  last_widget_summary?: string;
  recent_widget_feedback?: Array<{
    widget_id: string;
    widget_kind: string;
    summary?: string;
    status?: string;
    title?: string;
    visual_session_id?: string;
    score?: number;
    correct_count?: number;
    total_count?: number;
    source?: string;
    timestamp: string;
  }>;
}

export interface ChatCodeStudioContext {
  active_session?: {
    session_id: string;
    title: string;
    status: "streaming" | "complete" | "error";
    active_version: number;
    version_count: number;
    language: string;
    studio_lane: "app" | "artifact" | "widget";
    artifact_kind?: "html_app" | "code_widget" | "search_widget" | "document" | "chart_widget";
    quality_profile?: "draft" | "standard" | "premium";
    renderer_contract?: "host_shell" | "chart_runtime" | "article_figure";
    has_preview: boolean;
  };
  requested_view?: "code" | "preview";
}

export interface ChatUserContext {
  display_name?: string;
  role?: UserRole;
  page_context?: unknown | null;
  student_state?: unknown | null;
  available_actions?: unknown[] | null;
  host_context?: unknown | null;
  host_capabilities?: unknown | null;
  host_action_feedback?: unknown | null;
  visual_context?: ChatVisualContext | null;
  widget_feedback?: ChatWidgetFeedbackContext | null;
  code_studio_context?: ChatCodeStudioContext | null;
  document_context?: ChatDocumentContext | null;
  [key: string]: unknown;
}

export interface ChatRequest {
  user_id: string;
  message: string;
  role: UserRole;
  session_id?: string;
  thread_id?: string;
  domain_id?: string;
  organization_id?: string;
  images?: ImageInput[];
  user_context?: ChatUserContext;
  provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  model?: string;
  /** Wiii Pointy v2.8: explicit @plugin-name force-bind from chat input. */
  force_skills?: string[];
  /** F18 Phase B (2026-05-07) — Pointy mode flag. */
  pointy_mode?: boolean;
  /** Optional ElevenLabs-backed spoken Pointy captions. Audio is opt-in. */
  pointy_voice_enabled?: boolean;
}

export interface SourceInfo {
  title: string;
  content: string;
  url?: string;
  source_type?: string;
  image_url?: string;
  page_number?: number;
  document_id?: string;
  bounding_boxes?: Array<{
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  }>;
}

export interface ToolUsageInfo {
  name: string;
  description: string;
}

export interface ReasoningStep {
  step_name: string;
  description: string;
  result: string;
  confidence?: number;
  duration_ms: number;
  details?: Record<string, unknown>;
}

export interface ReasoningTrace {
  total_steps: number;
  total_duration_ms: number;
  was_corrected: boolean;
  correction_reason?: string;
  final_confidence: number;
  steps: ReasoningStep[];
}

export interface ThinkingLifecycleSegment {
  segment_id: string;
  turn_id: string;
  node: string;
  step_id?: string | null;
  sequence_id?: number | null;
  phase: "pre_tool" | "tool_continuation" | "post_tool" | "final_snapshot";
  provenance: "live_native" | "tool_continuation" | "final_snapshot" | "aligned_cleanup";
  status: "live" | "completed";
  display_role?: string | null;
  presentation?: string | null;
  label?: string | null;
  summary?: string | null;
  content: string;
  content_length: number;
  started_at?: number | null;
  ended_at?: number | null;
}

export interface ThinkingLifecycleSnapshot {
  version: number;
  turn_id: string;
  final_text: string;
  final_length: number;
  live_text: string;
  live_length: number;
  segment_count: number;
  has_tool_continuation: boolean;
  phases: Array<ThinkingLifecycleSegment["phase"]>;
  provenance_mix: Array<ThinkingLifecycleSegment["provenance"]>;
  segments: ThinkingLifecycleSegment[];
}

export interface FailoverRouteEvent {
  from_provider?: string | null;
  to_provider?: string | null;
  reason_code?: string | null;
  reason_category?: string | null;
  reason_label?: string | null;
  raw_reason?: string | null;
  error_type?: string | null;
  detail?: string | null;
  timeout_seconds?: number | null;
}

export interface FailoverMetadata {
  switched: boolean;
  switch_count: number;
  initial_provider?: string | null;
  final_provider?: string | null;
  last_reason_code?: string | null;
  last_reason_category?: string | null;
  last_reason_label?: string | null;
  route: FailoverRouteEvent[];
}

export interface ModelSwitchPromptOption {
  provider: "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  label: string;
  selected_model?: string | null;
}

export interface ModelSwitchPrompt {
  trigger: string;
  reason_code?: string | null;
  current_provider?: string | null;
  title: string;
  message: string;
  recommended_provider?: string | null;
  options: ModelSwitchPromptOption[];
  allow_retry_once: boolean;
  allow_session_switch: boolean;
}

export interface RuntimeFlowTrace {
  version?: string;
  turn_path_decision?: Record<string, unknown>;
  tool_policy_session?: Record<string, unknown>;
  external_app_action_plan?: Record<string, unknown>;
  external_app_integration_lane?: Record<string, unknown>;
  external_action_trace?: Record<string, unknown>;
  final_answer?: Record<string, unknown>;
}

export interface RuntimeFlowLedger {
  schema_version?: string;
  request?: Record<string, unknown>;
  context?: Record<string, unknown>;
  route?: Record<string, unknown>;
  runtime?: Record<string, unknown>;
  tools?: Record<string, unknown>;
  scheduled_tasks?: Record<string, unknown>;
  external_app?: Record<string, unknown>;
  stream?: Record<string, unknown>;
  host_actions?: Record<string, unknown>;
  finalization?: Record<string, unknown>;
  final_answer?: Record<string, unknown>;
}

export interface ChatResponseMetadata {
  processing_time: number;
  provider?: string;
  model: string;
  runtime_authoritative?: boolean;
  agent_type: "chat" | "rag" | "tutor" | "direct" | "memory" | "code_studio";
  session_id?: string;
  /** Sprint 225: Composite thread ID for cross-platform sync */
  thread_id?: string;
  tools_used?: ToolUsageInfo[];
  reasoning_trace?: ReasoningTrace;
  thinking_content?: string;
  thinking?: string;
  thinking_lifecycle?: ThinkingLifecycleSnapshot;
  chat_lifecycle?: ChatLifecycleTelemetryEvent[];
  failover?: FailoverMetadata | null;
  model_switch_prompt?: ModelSwitchPrompt | null;
  topics_accessed?: string[];
  confidence_score?: number;
  document_ids_used?: string[];
  query_type?: string;
  suggested_questions?: string[];
  data?: Record<string, unknown>;
  runtime_flow_trace?: RuntimeFlowTrace;
  runtime_flow_ledger?: RuntimeFlowLedger;
  /** Allow runtime-extended fields from server */
  [key: string]: unknown;
}

export interface ChatResponseData {
  answer: string;
  sources: SourceInfo[];
  suggested_questions: string[];
  domain_notice?: string;
  evidence_images?: Array<{
    url: string;
    page_number: number;
    document_id: string;
  }>;
}

export interface ToolResultMetadata {
  schema_version?: string;
  status?:
    | "completed"
    | "skipped"
    | "failed"
    | "validation_failed"
    | "blocked"
    | "needs_input"
    | "unavailable"
    | string;
  result_kind?:
    | "text"
    | "weather"
    | "web_sources"
    | "sources"
    | "policy"
    | "validation"
    | string;
  reason_code?: string;
  source_count?: number;
  domains?: string[];
  skipped?: boolean;
  policy?: Record<string, unknown>;
  missing_fields?: string[];
  [key: string]: unknown;
}

export interface SSEChatLifecycleEvent {
  schema_version: string;
  event_name: string;
  phase: string;
  status: string;
  message: string;
  request_id?: string;
  session_id?: string;
  lane?: string;
  reason?: string;
  node?: string;
  step?: string;
  capabilities?: {
    host_surface?: string;
    host_capabilities?: string[];
    observed_tools?: string[];
    suppressed_tools?: string[];
    preview_required?: boolean;
    preview_emitted?: boolean;
    approval_token_present?: boolean;
    apply_attempted?: boolean;
    wiii_connect?: WiiiConnectRuntimeSnapshot;
  };
  metadata?: Record<string, unknown>;
  details?: Record<string, unknown>;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface ChatLifecycleTelemetryEvent extends SSEChatLifecycleEvent {
  received_at_ms: number;
}

export interface ToolCallInfo {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  result?: string;
  node?: string;
  metadata?: ToolResultMetadata;
  sources?: SourceInfo[];
}
