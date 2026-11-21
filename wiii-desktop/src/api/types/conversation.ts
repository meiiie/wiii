import type {
  WidgetFeedbackItem,
  SourceInfo,
  ReasoningTrace,
  ToolUsageInfo,
  ToolCallInfo,
  ImageInput,
  ChatDocumentAttachment,
} from "./chat";
import type { ContentBlock, PreviewItemData } from "./content-blocks";
import type { ArtifactData } from "./artifacts";
import type { UserRole } from "./identity";

export interface Conversation {
  id: string;
  title: string;
  domain_id?: string;
  organization_id?: string;
  model_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  model?: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  session_id?: string;
  thread_id?: string;
  pinned?: boolean;
  message_count?: number;
  summary?: string;
  user_renamed?: boolean;  // Sprint 225: tracks if user explicitly renamed (prevents server title overwrite)
  widget_feedback?: WidgetFeedbackItem[];
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
  /** Sprint 166: Rich preview cards */
  previews?: PreviewItemData[];
  /** Sprint 167: Interactive artifacts */
  artifacts?: ArtifactData[];
  /** Sprint 179: User-attached images (multimodal vision) */
  images?: ImageInput[];
  /** Per-turn user-attached documents shown as chips; Markdown lives only in request context. */
  documents?: ChatDocumentAttachment[];
  is_streaming?: boolean;
  metadata?: Record<string, unknown>;
}

/** Sprint 140: Thinking display level — progressive disclosure */
export type ThinkingLevel = "minimal" | "balanced" | "detailed";

export interface AppSettings {
  server_url: string;
  api_key: string;
  llm_provider?: "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
  google_model?: string;
  openai_base_url?: string;
  openai_model?: string;
  openai_model_advanced?: string;
  openrouter_base_url?: string;
  openrouter_model?: string;
  openrouter_model_advanced?: string;
  nvidia_base_url?: string;
  nvidia_model?: string;
  nvidia_model_advanced?: string;
  zhipu_base_url?: string;
  zhipu_model?: string;
  zhipu_model_advanced?: string;
  openrouter_model_fallbacks?: string[];
  openrouter_provider_order?: string[];
  openrouter_allowed_providers?: string[];
  openrouter_ignored_providers?: string[];
  openrouter_allow_fallbacks?: boolean | null;
  openrouter_require_parameters?: boolean | null;
  openrouter_data_collection?: "allow" | "deny" | "";
  openrouter_zdr?: boolean | null;
  openrouter_provider_sort?: "price" | "latency" | "throughput" | "";
  ollama_base_url?: string;
  ollama_model?: string;
  ollama_keep_alive?: string;
  llm_failover_enabled?: boolean;
  llm_failover_chain?: string[];
  user_id: string;
  user_role: UserRole;
  display_name: string;
  default_domain: string;
  /** Sprint 156: Active organization ID (null = personal workspace) */
  organization_id?: string | null;
  theme: "light" | "dark" | "system";
  language: "vi" | "en";
  font_size?: "small" | "medium" | "large";
  show_thinking: boolean;
  show_reasoning_trace: boolean;
  /** F18 Phase B (2026-05-07) — Pointy mode: user talks directly to
   * cursor; backend forces tool_pointy_show per turn (deterministic
   * UI navigation, cursor-agent persona). */
  pointy_mode?: boolean;
  /** Optional ElevenLabs-backed spoken Pointy captions. Audio is opt-in. */
  pointy_voice_enabled?: boolean;
  streaming_version: "v1" | "v2" | "v3";
  /** Sprint 140: Thinking level — minimal (status only), balanced (collapsed), detailed (expanded) */
  thinking_level: ThinkingLevel;
  /** Sprint 154: Facebook cookie for logged-in search (optional) */
  facebook_cookie?: string;
  /** Sprint 166: Show rich preview cards */
  show_previews?: boolean;
  /** Sprint 167: Show interactive artifacts */
  show_artifacts?: boolean;
  /** Per-request model provider selection (persisted across reloads) */
  model_provider?: "auto" | "google" | "zhipu" | "openai" | "openrouter" | "nvidia" | "ollama";
}
