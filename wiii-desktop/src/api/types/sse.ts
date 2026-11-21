import type {
  DisplayRole,
  StepState,
  PresentationMode,
  ThinkingSummaryMode,
  ArtifactData,
  VisualPayload,
  VisualSessionStatus,
} from "./artifacts";
import type {
  SourceInfo,
  ReasoningTrace,
  ThinkingLifecycleSnapshot,
  FailoverMetadata,
  ModelSwitchPrompt,
  RuntimeFlowLedger,
  ToolResultMetadata,
} from "./chat";
import type { MoodType } from "./character";
import type { ProviderDisabledReasonCode } from "./llm";
import type { PreviewItemData } from "./content-blocks";

export interface SSEThinkingEvent {
  content: string;
  step?: string;
  node?: string;
  confidence?: number;
  details?: Record<string, unknown>;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEAnswerEvent {
  content: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSESourcesEvent {
  sources?: SourceInfo[];
  content?: SourceInfo[];
  tool_call_id?: string;
  tool_name?: string;
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEMetadataEvent {
  processing_time?: number;
  streaming_version?: string;
  reasoning_trace?: ReasoningTrace;
  thinking?: string;
  thinking_content?: string;
  thinking_lifecycle?: ThinkingLifecycleSnapshot;
  failover?: FailoverMetadata | null;
  model_switch_prompt?: ModelSwitchPrompt | null;
  /** Sprint 120: Mood state from backend emotional state machine */
  mood?: {
    positivity: number;
    energy: number;
    mood: MoodType;
  } | null;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
  [key: string]: unknown;
}

export interface SSEDoneEvent {
  status?: string;
  processing_time?: number;
  runtime_flow_ledger?: RuntimeFlowLedger;
  [key: string]: unknown;
}

export interface SSEErrorEvent {
  message: string;
  provider?: string;
  reason_code?: ProviderDisabledReasonCode | string | null;
  model_switch_prompt?: ModelSwitchPrompt | null;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
  [key: string]: unknown;
}

export interface SSEToolCallEvent {
  content: {
    name: string;
    args: Record<string, unknown>;
    id: string;
    metadata?: ToolResultMetadata;
    policy?: Record<string, unknown>;
  };
  node?: string;
  step?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEToolResultEvent {
  content: {
    name: string;
    result: string;
    id: string;
    metadata?: ToolResultMetadata;
  };
  node?: string;
  step?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEStatusEvent {
  content: string;
  step?: string;
  node?: string;
  /** Sprint 164: Extra details (e.g. aggregation decision) */
  details?: Record<string, unknown>;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEDomainNoticeEvent {
  content: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/** Sprint 135: Soul emotion event — LLM-driven avatar expression */
export interface SSEEmotionEvent {
  mood: MoodType;
  face: Partial<Record<string, number>>;
  intensity: number;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEThinkingDeltaEvent {
  content: string;
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/** Sprint 147: Bold action text event — narrative between thinking blocks */
export interface SSEActionTextEvent {
  content: string;
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/** Sprint 153: Browser screenshot event — Playwright visual transparency */
export interface SSEBrowserScreenshotEvent {
  content: {
    url: string;
    image: string;   // Base64 JPEG
    label: string;
  };
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEThinkingStartEvent {
  type: "thinking_start";
  content: string;  // label (Vietnamese node name)
  node?: string;
  block_id?: string;
  /** Sprint 145: One-line summary for Claude-like collapsed header */
  summary?: string;
  /** Whether summary is only metadata/header, not visible body fallback */
  summary_mode?: ThinkingSummaryMode;
  /** Runtime reasoning phase from backend contract */
  phase?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEThinkingEndEvent {
  type: "thinking_end";
  node?: string;
  duration_ms?: number;
  block_id?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export type SSEEventType =
  | "thinking"
  | "thinking_delta"
  | "answer"
  | "sources"
  | "metadata"
  | "chat_lifecycle"
  | "done"
  | "error"
  | "tool_call"
  | "tool_result"
  | "status"
  | "thinking_start"
  | "thinking_end"
  | "domain_notice"
  | "emotion"
  | "action_text"
  | "browser_screenshot"
  | "preview"
  | "artifact"
  | "visual"
  | "visual_open"
  | "visual_patch"
  | "visual_commit"
  | "visual_dispose";

/** Sprint 167: SSE artifact event */
export interface SSEArtifactEvent {
  content: ArtifactData;
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEVisualEvent {
  content: VisualPayload;
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEVisualCommitEvent {
  content: {
    visual_session_id: string;
    status?: VisualSessionStatus;
  };
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

export interface SSEVisualDisposeEvent {
  content: {
    visual_session_id: string;
    reason?: string;
    status?: VisualSessionStatus;
  };
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/** Sprint 166: SSE preview event */
export interface SSEPreviewEvent {
  content: PreviewItemData;
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/** Sprint 222b: SSE host_action event — AI requests an action from the host app */
export interface SSEHostActionEvent {
  content: {
    id: string;
    action: string;
    params?: Record<string, unknown>;
  };
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/**
 * Wiii Pointy SSE event — agent invokes ``tool_pointy_show`` /
 * ``tool_pointy_clear`` and the runtime emits this to drive the
 * collaborator cursor / spotlight overlay.
 *
 * The action / params shape mirrors the existing ``PointyFastPathAction``
 * so the same in-app handlers (``handleHighlight`` / ``handleCursorMove``
 * from ``pointy-host/bridge.ts``) can run without a translation layer.
 * See ``app/engine/skills/library/wiii-pointy/SKILL.md`` for trigger
 * taxonomy and caption guidance.
 */
export interface SSEPointyActionEvent {
  content: {
    action: "ui.highlight" | "ui.cursor_move" | "ui.clear";
    requestId: string;
    params: {
      selector?: string;
      message?: string;
      duration_ms?: number;
      x?: number;
      y?: number;
      coordinate_space?: "viewport" | "normalized";
      label?: string;
      source: string;
    };
    mode: "highlight" | "cursor" | "clear";
  };
  node?: string;
  display_role?: DisplayRole;
  sequence_id?: number;
  step_id?: string;
  step_state?: StepState;
  presentation?: PresentationMode;
}

/** Code Studio: session opened */
export interface SSECodeOpenEvent {
  content: {
    session_id: string;
    title: string;
    language: string;
    version: number;
    studio_lane?: "app" | "artifact" | "widget";
    artifact_kind?: "html_app" | "code_widget" | "search_widget" | "document" | "chart_widget";
    quality_profile?: "draft" | "standard" | "premium";
    renderer_contract?: "host_shell" | "chart_runtime" | "article_figure";
    requested_view?: "code" | "preview";
  };
  node?: string;
}

/** Code Studio: chunked code content */
export interface SSECodeDeltaEvent {
  content: {
    session_id: string;
    chunk: string;
    chunk_index: number;
    total_bytes: number;
  };
  node?: string;
}

/** Code Studio: full code + trigger preview */
export interface SSECodeCompleteEvent {
  content: {
    session_id: string;
    full_code: string;
    language: string;
    version: number;
    studio_lane?: "app" | "artifact" | "widget";
    artifact_kind?: "html_app" | "code_widget" | "search_widget" | "document" | "chart_widget";
    quality_profile?: "draft" | "standard" | "premium";
    renderer_contract?: "host_shell" | "chart_runtime" | "article_figure";
    requested_view?: "code" | "preview";
    visual_payload?: VisualPayload;
    /** Maps streaming session to the visual_open session for frontend unification */
    visual_session_id?: string;
  };
  node?: string;
}
