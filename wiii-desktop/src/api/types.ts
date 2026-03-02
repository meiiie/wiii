/**
 * TypeScript types mirroring the Wiii backend Pydantic schemas.
 * Source: maritime-ai-service/app/models/schemas.py
 */

// ===== Enums =====
export type UserRole = "student" | "teacher" | "admin";

// ===== Sprint 179: Multimodal Vision Input =====
export interface ImageInput {
  type: "base64" | "url";
  media_type: string;
  data: string;
  detail?: "auto" | "low" | "high";
}

// ===== Chat Request =====
export interface ChatRequest {
  user_id: string;
  message: string;
  role: UserRole;
  session_id?: string;
  thread_id?: string;
  domain_id?: string;
  organization_id?: string;
  images?: ImageInput[];
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
  agent_type: "chat" | "rag" | "tutor";
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
  /** Sprint 164: Extra details (e.g. aggregation decision) */
  details?: Record<string, unknown>;
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
  | "browser_screenshot"
  | "preview"
  | "artifact";

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
  /** Sprint 164: Parent subagent group ID (for grouped rendering) */
  groupId?: string;
  /** Sprint 164: Agent name within the parallel group */
  workerNode?: string;
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
  image: string;           // Base64 JPEG — kept permanently
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
export interface SubagentGroupBlockData {
  type: "subagent_group";
  id: string;
  label: string;
  workers: SubagentWorker[];
  aggregation?: AggregationSummary;
  startTime: number;
  endTime?: number;
}

// ===== Execution Result (Sprint 167b: deduplicated from artifact-sandbox + pyodide-runtime) =====
export interface ExecutionResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  images: string[];      // base64 PNG from matplotlib
  tables: unknown[][];   // pandas DataFrame as arrays
  executionTime: number;  // ms
}

// ===== Artifact System (Sprint 167) =====
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

export interface ArtifactBlockData {
  type: "artifact";
  id: string;
  artifact: ArtifactData;
  node?: string;
}

/** Sprint 167: SSE artifact event */
export interface SSEArtifactEvent {
  content: ArtifactData;
  node?: string;
}

// ===== Preview System (Sprint 166) =====
export type PreviewType = "document" | "product" | "web" | "link" | "code";

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

export interface PreviewBlockData {
  type: "preview";
  id: string;
  items: PreviewItemData[];
  node?: string;
}

/** Sprint 166: SSE preview event */
export interface SSEPreviewEvent {
  content: PreviewItemData;
  node?: string;
}

/** Sprint 222b: SSE host_action event — AI requests an action from the host app */
export interface SSEHostActionEvent {
  content: {
    id: string;
    action: string;
    params?: Record<string, unknown>;
  };
  node?: string;
}

/** Ordered content block — enables interleaved thinking+answer rendering */
export type ContentBlock = ThinkingBlockData | AnswerBlockData | ActionTextBlockData | ScreenshotBlockData | SubagentGroupBlockData | PreviewBlockData | ArtifactBlockData;

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

// ===== Organization (Sprint 156) =====
export interface OrganizationSummary {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  allowed_domains: string[];
  default_domain?: string;
  is_active: boolean;
}

// ===== Org Settings (Sprint 161) =====
export interface OrgBranding {
  logo_url: string | null;
  primary_color: string;
  accent_color: string;
  welcome_message: string;
  chatbot_name: string;
  chatbot_avatar_url: string | null;
  institution_type: string;
}

export interface OrgFeatureFlags {
  enable_product_search: boolean;
  enable_deep_scanning: boolean;
  enable_thinking_chain: boolean;
  enable_browser_scraping: boolean;
  visible_agents: string[];
  max_search_iterations: number;
}

export interface OrgPermissions {
  student: string[];
  teacher: string[];
  admin: string[];
}

export interface OrgOnboarding {
  quick_start_questions: string[];
  show_domain_suggestions: boolean;
}

export interface OrgSettings {
  schema_version: number;
  branding: OrgBranding;
  features: OrgFeatureFlags;
  ai_config: {
    persona_prompt_overlay: string | null;
    temperature_override: number | null;
    max_response_length: number | null;
    default_domain: string | null;
  };
  permissions: OrgPermissions;
  onboarding: OrgOnboarding;
}

export interface OrgPermissionsResponse {
  permissions: string[];
  role: string;
  organization_id: string;
  org_role?: string | null;  // Sprint 215: member | admin | owner
}

// ===== Health =====
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  components?: Record<string, {
    name: string;
    status: "healthy" | "degraded" | "unavailable";
    latency_ms?: number;
    message?: string;
  }>;
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

export interface ClearMemoriesResponse {
  success: boolean;
  deleted_count: number;
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

// ===== User Profile (Sprint 158) =====
export interface UserProfile {
  id: string;
  email?: string;
  name?: string;
  avatar_url?: string;
  role: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserIdentity {
  id: string;
  provider: string;
  provider_sub: string;
  provider_issuer?: string;
  email?: string;
  display_name?: string;
  avatar_url?: string;
  linked_at?: string;
  last_used_at?: string;
}

// ===== Local types (desktop-only) =====
export interface Conversation {
  id: string;
  title: string;
  domain_id?: string;
  organization_id?: string;
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
  /** Sprint 166: Rich preview cards */
  previews?: PreviewItemData[];
  /** Sprint 167: Interactive artifacts */
  artifacts?: ArtifactData[];
  /** Sprint 179: User-attached images (multimodal vision) */
  images?: ImageInput[];
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
  /** Sprint 156: Active organization ID (null = personal workspace) */
  organization_id?: string | null;
  theme: "light" | "dark" | "system";
  language: "vi" | "en";
  font_size?: "small" | "medium" | "large";
  show_thinking: boolean;
  show_reasoning_trace: boolean;
  streaming_version: "v1" | "v2" | "v3";
  /** Sprint 140: Thinking level — minimal (status only), balanced (collapsed), detailed (expanded) */
  thinking_level: ThinkingLevel;
  /** Sprint 154: Facebook cookie for logged-in search (optional) */
  facebook_cookie?: string;
  /** Sprint 166: Show rich preview cards */
  show_previews?: boolean;
  /** Sprint 167: Show interactive artifacts */
  show_artifacts?: boolean;
}

// ===== Sprint 170: Living Agent Types =====

/** Wiii's mood types */
export type WiiiMoodType =
  | "curious"
  | "happy"
  | "excited"
  | "focused"
  | "calm"
  | "tired"
  | "concerned"
  | "reflective"
  | "proud"
  | "neutral";

/** Skill development status */
export type SkillStatus =
  | "discovered"
  | "learning"
  | "practicing"
  | "evaluating"
  | "mastered"
  | "archived";

/** Emotional state response */
export interface LivingAgentEmotionalState {
  primary_mood: WiiiMoodType;
  energy_level: number;
  social_battery: number;
  engagement: number;
  mood_label: string;
  behavior_modifiers: Record<string, string>;
  last_updated: string | null;
}

/** Heartbeat info */
export interface LivingAgentHeartbeat {
  is_running: boolean;
  heartbeat_count: number;
  interval_seconds: number;
  active_hours: string;
}

/** Overall living agent status */
export interface LivingAgentStatus {
  enabled: boolean;
  emotional_state: LivingAgentEmotionalState | null;
  heartbeat: LivingAgentHeartbeat | null;
  skills_count: number;
  journal_entries_count: number;
  soul_loaded: boolean;
  soul_name: string;
}

/** Journal entry */
export interface LivingAgentJournalEntry {
  id: string;
  entry_date: string;
  content: string;
  mood_summary: string;
  energy_avg: number;
  notable_events: string[];
  learnings: string[];
  goals_next: string[];
}

/** Tracked skill */
export interface LivingAgentSkill {
  id: string;
  skill_name: string;
  domain: string;
  status: SkillStatus;
  confidence: number;
  usage_count: number;
  success_rate: number;
  discovered_at: string | null;
  last_practiced: string | null;
  mastered_at: string | null;
}

/** Heartbeat trigger result */
export interface HeartbeatTriggerResult {
  success: boolean;
  actions_taken: number;
  duration_ms: number;
  error: string | null;
}

// ===== Sprint 210: Goals & Reflections Types =====

/** Goal status */
export type GoalStatus = "proposed" | "active" | "completed" | "abandoned";

/** A dynamic goal */
export interface LivingAgentGoal {
  id: string;
  title: string;
  description: string;
  status: GoalStatus;
  priority: string;
  progress: number;
  source: string;
  milestones: string[];
  completed_milestones: string[];
  created_at: string | null;
  target_date: string | null;
  completed_at: string | null;
}

/** A reflection entry */
export interface LivingAgentReflection {
  id: string;
  content: string;
  insights: string[];
  goals_next_week: string[];
  patterns_noticed: string[];
  emotion_trend: string;
  reflection_date: string | null;
}

// ===== Sprint 179: Admin Panel Types =====

/** Sprint 179b: Organization summary in dashboard */
export interface AdminOrgSummary {
  id: string;
  name: string;
  display_name: string | null;
  member_count: number;
  document_count?: number;  // Sprint 190: Org knowledge docs
  is_active: boolean;
}

/** Sprint 179b: Organization detail (from /organizations/{id}) */
export interface AdminOrgDetail {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  allowed_domains: string[];
  default_domain: string | null;
  settings: OrgSettings | null;
  document_count?: number;  // Sprint 190: Org knowledge docs
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** Sprint 179b: Organization member */
export interface AdminOrgMember {
  user_id: string;
  organization_id: string;
  role: string;
  joined_at: string | null;
}

// ===== Sprint 181: Admin Context (Two-Tier Admin) =====

/** GET /users/me/admin-context */
export interface AdminContext {
  is_system_admin: boolean;
  is_org_admin: boolean;
  admin_org_ids: string[];
  enable_org_admin: boolean;
}

/** GET /admin/dashboard */
export interface AdminDashboard {
  total_users: number;
  active_users: number;
  total_organizations: number;
  total_chat_sessions_24h: number;
  total_llm_tokens_24h: number;
  estimated_cost_24h_usd: number;
  feature_flags_active: number;
  /** Sprint 179b: Organization list in dashboard */
  organizations?: AdminOrgSummary[];
}

/** User row in admin search */
export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
  organization_count: number;
}

/** GET /admin/users params */
export interface AdminUserSearchParams {
  q?: string;
  email?: string;
  role?: string;
  org_id?: string;
  status?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}

/** GET /admin/users response */
export interface AdminUserSearchResponse {
  users: AdminUser[];
  total: number;
  limit: number;
  offset: number;
}

/** Feature flag entry */
export interface AdminFeatureFlag {
  key: string;
  value: boolean;
  source: "config" | "db_override";
  flag_type: string;
  description: string | null;
  owner: string | null;
  expires_at: string | null;
}

/** PATCH /admin/feature-flags/{key} body */
export interface AdminFlagUpdateBody {
  value: boolean;
  flag_type?: string | null;
  description?: string | null;
  organization_id?: string | null;
  expires_at?: string | null;
}

/** Analytics overview response */
export interface AnalyticsOverview {
  period_start: string;
  period_end: string;
  daily_active_users: AnalyticsDataPoint[];
  chat_volume: ChatVolumePoint[];
  error_rate: ErrorRatePoint[];
}

export interface AnalyticsDataPoint {
  date: string;
  count: number;
}

export interface ChatVolumePoint {
  date: string;
  messages: number;
  sessions: number;
}

export interface ErrorRatePoint {
  date: string;
  total: number;
  errors: number;
  rate: number;
}

/** LLM usage analytics */
export interface LlmUsageAnalytics {
  total_tokens: number;
  total_cost_usd: number;
  total_requests: number;
  breakdown: LlmUsageBreakdown[];
  top_models: { model: string; tokens: number; requests: number }[];
  top_users: { user_id: string; tokens: number; requests: number }[];
}

export interface LlmUsageBreakdown {
  group: string;
  tokens: number;
  cost: number;
  requests: number;
}

/** User analytics */
export interface UserAnalytics {
  total_users: number;
  new_users_period: number;
  active_users_period: number;
  user_growth: UserGrowthPoint[];
  role_distribution: Record<string, number>;
  top_active_users: { user_id: string; sessions: number }[];
}

export interface UserGrowthPoint {
  date: string;
  new_users: number;
}

/** Admin audit log entry */
export interface AdminAuditEntry {
  id: string;
  actor_id: string;
  actor_role: string;
  actor_name: string;
  action: string;
  http_method: string;
  http_path: string;
  http_status: number;
  target_type: string;
  target_id: string;
  target_name: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  ip_address: string;
  request_id: string;
  organization_id: string | null;
  occurred_at: string | null;
}

/** GET /admin/audit-logs response */
export interface AdminAuditLogsResponse {
  entries: AdminAuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

/** Auth event entry */
export interface AdminAuthEvent {
  id: string;
  event_type: string;
  user_id: string;
  provider: string;
  result: string;
  reason: string | null;
  ip_address: string;
  organization_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

/** GET /admin/auth-events response */
export interface AdminAuthEventsResponse {
  entries: AdminAuthEvent[];
  total: number;
  limit: number;
  offset: number;
}

/** GDPR export response */
export interface GdprExportResponse {
  user_id: string;
  exported_at: string;
  data: {
    profile: Record<string, unknown>;
    identities: Record<string, unknown>[];
    memories: Record<string, unknown>[];
    auth_events: Record<string, unknown>[];
    audit_entries: Record<string, unknown>[];
  };
}

// ===== Sprint 190: Org Knowledge Management =====

export type OrgDocumentStatus = "uploading" | "processing" | "ready" | "failed" | "deleted";

export interface OrgDocument {
  document_id: string;
  organization_id: string;
  filename: string;
  file_size_bytes: number | null;
  status: OrgDocumentStatus;
  page_count: number | null;
  chunk_count: number | null;
  error_message: string | null;
  uploaded_by: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface OrgDocumentListResponse {
  documents: OrgDocument[];
  total: number;
}

// ===== Sprint 191: Knowledge Visualization =====

export interface ScatterPoint {
  x: number;
  y: number;
  z?: number | null;
  document_id: string;
  document_name: string;
  content_preview: string;
  content_type?: string | null;
  page_number?: number | null;
}

export interface ScatterDocument {
  id: string;
  name: string;
  color: string;
}

export interface ScatterResponse {
  points: ScatterPoint[];
  documents: ScatterDocument[];
  method: string;
  dimensions: number;
  computation_ms: number;
}

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  node_type: "document" | "chunk";
  document_id?: string | null;
  page_number?: number | null;
}

export interface KnowledgeGraphEdge {
  source: string;
  target: string;
  edge_type: "contains" | "similar_to";
  weight?: number | null;
}

export interface KnowledgeGraphResponse {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  mermaid_code: string;
  computation_ms: number;
}

export interface RagFlowStep {
  name: string;
  duration_ms: number;
  detail?: string | null;
}

export interface RagFlowChunk {
  chunk_id: string;
  document_id: string;
  document_name: string;
  content_preview: string;
  page_number?: number | null;
  similarity: number;
  grade: "relevant" | "partial" | "irrelevant";
  content_type?: string | null;
}

export interface RagFlowResponse {
  query: string;
  steps: RagFlowStep[];
  chunks: RagFlowChunk[];
  computation_ms: number;
}

/** GDPR forget response */
export interface GdprForgetResponse {
  user_id: string;
  status: string;
  profile_anonymized: boolean;
  identities_deleted: number;
  tokens_revoked: number;
  memories_deleted: number;
  audit_logs_preserved: boolean;
}
