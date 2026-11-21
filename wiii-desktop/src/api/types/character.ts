export interface CharacterBlockInfo {
  label: string;
  content: string;
  char_limit: number;
  usage_percent: number;
}

export interface CharacterCardInfo {
  card_id: string;
  card_name: string;
  card_kind: string;
  card_family: string;
  contract_version: string;
  name: string;
  summary: string;
  origin: string;
  greeting: string;
  traits: string[];
  quirks: string[];
  core_truths: string[];
  reasoning_style: string[];
  relationship_style: string[];
  anti_drift: string[];
  runtime_notes: string[];
}

export interface CharacterStateResponse {
  blocks: CharacterBlockInfo[];
  total_blocks: number;
  card?: CharacterCardInfo | null;
}

export type MoodType = "excited" | "warm" | "concerned" | "gentle" | "neutral";

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
