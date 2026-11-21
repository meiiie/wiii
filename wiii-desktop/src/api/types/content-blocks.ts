import type {
  DisplayPresentationMeta,
  ThinkingSummaryMode,
  VisualBlockData,
  ArtifactBlockData,
} from "./artifacts";
import type { ToolCallInfo } from "./chat";

/** Pipeline progress step (separate from AI thinking content) */
export interface StreamingStep {
  label: string;
  node?: string;
  timestamp: number;
}

/** A thinking block with optional inline tool calls */
export interface ThinkingBlockData extends DisplayPresentationMeta {
  type: "thinking";
  id: string;
  label?: string;
  /** Sprint 145: One-line summary for Claude-like collapsed header */
  summary?: string;
  summaryMode?: ThinkingSummaryMode;
  /** Backend node that produced this thinking block */
  node?: string;
  /** Runtime reasoning phase from backend contract */
  phase?: string;
  content: string;
  toolCalls: ToolCallInfo[];
  /** epoch ms when block was created (for duration) */
  startTime?: number;
  /** epoch ms when block was closed (next block started) */
  endTime?: number;
  /** Sprint 164: Parent subagent group ID (for grouped rendering) */
  groupId?: string;
  /** Sprint 164: Agent name within the parallel group */
  workerNode?: string;
}

export interface ToolExecutionBlockData extends DisplayPresentationMeta {
  type: "tool_execution";
  id: string;
  tool: ToolCallInfo;
  node?: string;
  status: "pending" | "completed";
  outcome?: "completed" | "failed" | "cancelled";
}

/** An answer/content block with markdown text */
export interface AnswerBlockData extends DisplayPresentationMeta {
  type: "answer";
  id: string;
  content: string;
}

/** Sprint 147: Bold narrative text between thinking blocks (Claude-style action text) */
export interface ActionTextBlockData extends DisplayPresentationMeta {
  type: "action_text";
  id: string;
  content: string;
  /** Sprint 149: Source agent node for attribution */
  node?: string;
}

/** Sprint 153: Browser screenshot block — Playwright visual transparency */
export interface ScreenshotBlockData extends DisplayPresentationMeta {
  type: "screenshot";
  id: string;
  url: string;
  image: string;           // Base64 JPEG - kept permanently
  label: string;
  node?: string;
}

/** Sprint 164: Subagent worker status within a parallel dispatch group */
export interface SubagentWorker {
  agentName: string;
  label: string;
  status: "active" | "completed" | "error";
  startTime: number;
  endTime?: number;
  /** Status messages for per-worker progress display */
  statusMessages: string[];
}

/** Sprint 164: Aggregation decision summary from the aggregator node */
export interface AggregationSummary {
  strategy: string;
  primaryAgent?: string;
  confidence: number;
  reasoning: string;
}

/** Sprint 164: Subagent group block — visual container for parallel dispatch */
export interface SubagentGroupBlockData extends DisplayPresentationMeta {
  type: "subagent_group";
  id: string;
  label: string;
  workers: SubagentWorker[];
  aggregation?: AggregationSummary;
  startTime: number;
  endTime?: number;
}

export type PreviewType = "document" | "product" | "web" | "link" | "code" | "host_action";

export interface PreviewItemData {
  preview_type: PreviewType;
  preview_id: string;
  title: string;
  snippet?: string;
  url?: string;
  image_url?: string;
  citation_index?: number;
  metadata?: Record<string, unknown>;
}

export interface PreviewBlockData extends DisplayPresentationMeta {
  type: "preview";
  id: string;
  items: PreviewItemData[];
  node?: string;
}

/** Ordered content block - enables interleaved thinking+answer rendering */
export type ContentBlock =
  | ThinkingBlockData
  | ToolExecutionBlockData
  | AnswerBlockData
  | ActionTextBlockData
  | ScreenshotBlockData
  | SubagentGroupBlockData
  | VisualBlockData
  | PreviewBlockData
  | ArtifactBlockData;

/** Sprint 141: Unified thinking phase for ThinkingFlow component */
export interface ThinkingPhase {
  id: string;
  label: string;              // Vietnamese label from thinking_start
  node?: string;              // Backend node name
  stepId?: string;            // Stable SSE step_id / block_id for interval grouping
  phase?: string;             // Backend reasoning phase label
  summary?: string;           // One-line summary from thinking_start
  summaryMode?: ThinkingSummaryMode;
  status: "active" | "completed";
  startTime: number;
  endTime?: number;
  thinkingContent: string;    // AI reasoning (from thinking/thinking_delta)
  toolCalls: ToolCallInfo[];  // Inline tool cards
  statusMessages: string[];   // Status updates within this phase
}
