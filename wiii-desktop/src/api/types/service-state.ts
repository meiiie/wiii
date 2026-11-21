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

export interface MemoryItem {
  id: string;
  type: string;
  value: string;
  created_at: string;
}

export interface MemoryHealthSummary {
  total: number;
  type_counts: Record<string, number>;
  latest_created_at: string | null;
  scope_state: string;
  org_scoped: boolean;
  controls: {
    can_delete_one: boolean;
    can_clear_all: boolean;
  };
  provenance: {
    source_kinds: Record<string, number>;
    raw_content_included: boolean;
    identifier_strategy: string;
  };
  privacy: {
    raw_content_included: boolean;
    identifier_strategy: string;
  };
}

export interface MemoryListResponse {
  data: MemoryItem[];
  total: number;
  summary?: MemoryHealthSummary;
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
