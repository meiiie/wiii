/**
 * TypeScript types mirroring the Wiii backend Pydantic schemas.
 * Source: maritime-ai-service/app/models/schemas.py
 */

// ===== Enums =====
export type UserRole = "student" | "teacher" | "admin";
export type AgentType = "chat" | "rag" | "tutor";
export type ComponentStatus = "healthy" | "degraded" | "unavailable";

// ===== Chat Request =====
export interface UserContext {
  display_name: string;
  role: UserRole;
  level?: string;
  organization?: string;
  current_course_id?: string;
  current_course_name?: string;
  current_module_id?: string;
  current_module_name?: string;
  progress_percent?: number;
  completed_modules?: string[];
  quiz_scores?: Record<string, number>;
  language?: string;
}

export interface ChatRequest {
  user_id: string;
  message: string;
  role: UserRole;
  session_id?: string;
  thread_id?: string;
  user_context?: UserContext;
  domain_id?: string;
}

// ===== Chat Response =====
export interface SourceInfo {
  title: string;
  content: string;
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

export interface ChatResponseMetadata {
  processing_time: number;
  model: string;
  agent_type: AgentType;
  session_id?: string;
  tools_used?: ToolUsageInfo[];
  reasoning_trace?: ReasoningTrace;
  thinking_content?: string;
  thinking?: string;
  topics_accessed?: string[];
  confidence_score?: number;
  document_ids_used?: string[];
  query_type?: string;
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

export interface ChatResponse {
  status: "success" | "error";
  data: ChatResponseData;
  metadata: ChatResponseMetadata;
}

// ===== SSE Events (v3 streaming) =====
export interface SSEThinkingEvent {
  content: string;
  step?: string;
  node?: string;
  confidence?: number;
  details?: Record<string, unknown>;
}

export interface SSEAnswerEvent {
  content: string;
}

export interface SSESourcesEvent {
  sources: SourceInfo[];
}

export interface SSEMetadataEvent {
  processing_time?: number;
  streaming_version?: string;
  reasoning_trace?: ReasoningTrace;
  thinking?: string;
  thinking_content?: string;
  /** Sprint 120: Mood state from backend emotional state machine */
  mood?: {
    positivity: number;
    energy: number;
    mood: MoodType;
  } | null;
  [key: string]: unknown;
}

export interface SSEDoneEvent {
  status: "complete";
}

export interface SSEErrorEvent {
  message: string;
}

export interface SSEToolCallEvent {
  content: {
    name: string;
    args: Record<string, unknown>;
    id: string;
  };
  node?: string;
  step?: string;
}

export interface SSEToolResultEvent {
  content: {
    name: string;
    result: string;
    id: string;
  };
  node?: string;
  step?: string;
}

export interface SSEStatusEvent {
  content: string;
  step?: string;
  node?: string;
}

export interface SSEDomainNoticeEvent {
  content: string;
}

/** Sprint 135: Soul emotion event — LLM-driven avatar expression */
export interface SSEEmotionEvent {
  mood: MoodType;
  face: Partial<Record<string, number>>;
  intensity: number;
}

export interface SSEThinkingDeltaEvent {
  content: string;
  node?: string;
}

/** Sprint 147: Bold action text event — narrative between thinking blocks */
export interface SSEActionTextEvent {
  content: string;
  node?: string;
}

/** Sprint 153: Browser screenshot event — Playwright visual transparency */
export interface SSEBrowserScreenshotEvent {
  content: {
    url: string;
    image: string;   // Base64 JPEG
    label: string;
  };
  node?: string;
}

export interface SSEThinkingStartEvent {
  type: "thinking_start";
  content: string;  // label (Vietnamese node name)
  node?: string;
  block_id?: string;
  /** Sprint 145: One-line summary for Claude-like collapsed header */
  summary?: string;
}

export interface SSEThinkingEndEvent {
  type: "thinking_end";
  node?: string;
  duration_ms?: number;
  block_id?: string;
}

export type SSEEventType =
  | "thinking"
  | "thinking_delta"
  | "answer"
  | "sources"
  | "metadata"
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
  | "browser_screenshot";

export interface ToolCallInfo {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  result?: string;
  node?: string;
}

// ===== Streaming Progress =====

/** Pipeline progress step (separate from AI thinking content) */
export interface StreamingStep {
  label: string;
  node?: string;
  timestamp: number;
}

// ===== Content Blocks (interleaved thinking/answer) =====

/** A thinking block with optional inline tool calls */
export interface ThinkingBlockData {
  type: "thinking";
  id: string;
  label?: string;
  /** Sprint 145: One-line summary for Claude-like collapsed header */
  summary?: string;
  content: string;
  toolCalls: ToolCallInfo[];
  /** epoch ms when block was created (for duration) */
  startTime?: number;
  /** epoch ms when block was closed (next block started) */
  endTime?: number;
}

/** An answer/content block with markdown text */
export interface AnswerBlockData {
  type: "answer";
  id: string;
  content: string;
}

/** Sprint 147: Bold narrative text between thinking blocks (Claude-style action text) */
export interface ActionTextBlockData {
  type: "action_text";
  id: string;
  content: string;
  /** Sprint 149: Source agent node for attribution */
  node?: string;
}

/** Sprint 153: Browser screenshot block — Playwright visual transparency */
export interface ScreenshotBlockData {
  type: "screenshot";
  id: string;
  url: string;
  image: string;       // Base64 JPEG
  label: string;
  node?: string;
}

/** Ordered content block — enables interleaved thinking+answer rendering */
export type ContentBlock = ThinkingBlockData | AnswerBlockData | ActionTextBlockData | ScreenshotBlockData;

/** Sprint 141: Unified thinking phase for ThinkingFlow component */
export interface ThinkingPhase {
  id: string;
  label: string;              // Vietnamese label from thinking_start
  node?: string;              // Backend node name
  status: "active" | "completed";
  startTime: number;
  endTime?: number;
  thinkingContent: string;    // AI reasoning (from thinking/thinking_delta)
  toolCalls: ToolCallInfo[];  // Inline tool cards
  statusMessages: string[];   // Status updates within this phase
}

// ===== Domain =====
export interface DomainSummary {
  id: string;
  name: string;
  name_vi?: string;
  version: string;
  description: string;
  skill_count: number;
  keyword_count: number;
}

// ===== Health =====
export interface HealthComponent {
  name: string;
  status: ComponentStatus;
  latency_ms?: number;
  message?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  components?: Record<string, HealthComponent>;
}

// ===== Thread Management (Sprint 16: Server-side conversation index) =====
export interface ThreadView {
  thread_id: string;
  user_id: string;
  domain_id: string;
  title?: string;
  message_count: number;
  last_message_at?: string;
  created_at?: string;
  updated_at?: string;
  extra_data: Record<string, unknown>;
}

export interface ThreadListResponse {
  status: string;
  threads: ThreadView[];
  total: number;
}

export interface ThreadActionResponse {
  status: string;
  message: string;
}

// ===== Context Management (Sprint 78/80) =====
export interface ContextLayerInfo {
  budget: number;
  used: number;
}

export interface ContextInfoResponse {
  effective_window: number;
  max_output: number;
  total_budget: number;
  total_used: number;
  utilization: number;
  needs_compaction: boolean;
  layers: {
    system_prompt: ContextLayerInfo;
    core_memory: ContextLayerInfo;
    summary: ContextLayerInfo;
    recent_messages: ContextLayerInfo;
  };
  messages_included: number;
  messages_dropped: number;
  has_summary: boolean;
  session_id: string;
  running_summary_chars: number;
  total_history_messages: number;
}

export interface CompactResponse {
  status: string;
  session_id: string;
  summary_length: number;
  messages_summarized: number;
  message: string;
}

export interface ClearContextResponse {
  status: string;
  session_id: string;
  message: string;
}

// ===== Memory Management (Sprint 80) =====
export interface MemoryItem {
  id: string;
  type: string;
  value: string;
  created_at: string;
}

export interface MemoryListResponse {
  data: MemoryItem[];
  total: number;
}

export interface DeleteMemoryResponse {
  success: boolean;
  message: string;
}

// ===== Character State (Sprint 120) =====
export interface CharacterBlockInfo {
  label: string;
  content: string;
  char_limit: number;
  usage_percent: number;
}

export interface CharacterStateResponse {
  blocks: CharacterBlockInfo[];
  total_blocks: number;
}

// ===== Mood / Emotional State (Sprint 120) =====
export type MoodType = "excited" | "warm" | "concerned" | "gentle" | "neutral";

export interface MoodResponse {
  positivity: number;
  energy: number;
  mood: MoodType;
  mood_hint: string;
  enabled: boolean;
}

// ===== User Preferences (Sprint 120) =====
export type LearningStyle = "quiz" | "visual" | "reading" | "mixed" | "interactive";
export type DifficultyLevel = "beginner" | "intermediate" | "advanced" | "expert";
export type PronounStyle = "auto" | "formal" | "casual";

export interface UserPreferences {
  preferred_domain: string;
  language: string;
  pronoun_style: PronounStyle;
  learning_style: LearningStyle;
  difficulty: DifficultyLevel;
  timezone: string;
}

export interface UserPreferencesUpdate {
  preferred_domain?: string;
  language?: string;
  pronoun_style?: PronounStyle;
  learning_style?: LearningStyle;
  difficulty?: DifficultyLevel;
  timezone?: string;
}

// ===== Local types (desktop-only) =====
export interface Conversation {
  id: string;
  title: string;
  domain_id?: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  session_id?: string;
  thread_id?: string;
  pinned?: boolean;
  message_count?: number;
  summary?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: SourceInfo[];
  suggested_questions?: string[];
  thinking?: string;
  reasoning_trace?: ReasoningTrace;
  tools_used?: ToolUsageInfo[];
  tool_calls?: ToolCallInfo[];
  /** Ordered content blocks — interleaved thinking + answer. New in Sprint 62. */
  blocks?: ContentBlock[];
  /** Sprint 80b: Gentle notice when content is outside active domain */
  domain_notice?: string;
  /** Sprint 107: User feedback rating */
  feedback?: "up" | "down" | null;
  is_streaming?: boolean;
  metadata?: Record<string, unknown>;
}

/** Sprint 140: Thinking display level — progressive disclosure */
export type ThinkingLevel = "minimal" | "balanced" | "detailed";

export interface AppSettings {
  server_url: string;
  api_key: string;
  user_id: string;
  user_role: UserRole;
  display_name: string;
  default_domain: string;
  theme: "light" | "dark" | "system";
  language: "vi" | "en";
  font_size: "small" | "medium" | "large";
  show_thinking: boolean;
  show_reasoning_trace: boolean;
  streaming_version: "v1" | "v2" | "v3";
  /** Sprint 140: Thinking level — minimal (status only), balanced (collapsed), detailed (expanded) */
  thinking_level: ThinkingLevel;
}
