/**
 * Living Agent API module — Sprint 170: "Linh Hồn Sống"
 *
 * Endpoints for monitoring and interacting with Wiii's autonomous life.
 */
import type {
  LivingAgentStatus,
  LivingAgentEmotionalState,
  LivingAgentJournalEntry,
  LivingAgentSkill,
  LivingAgentHeartbeat,
  HeartbeatTriggerResult,
} from "./types";
import { getClient } from "./client";

const PREFIX = "/api/v1/living-agent";

/** Get overall living agent status */
export async function getLivingAgentStatus(): Promise<LivingAgentStatus> {
  const client = getClient();
  return client.get<LivingAgentStatus>(`${PREFIX}/status`);
}

/** Get current emotional state */
export async function getEmotionalState(): Promise<LivingAgentEmotionalState> {
  const client = getClient();
  return client.get<LivingAgentEmotionalState>(`${PREFIX}/emotional-state`);
}

/** Get recent journal entries */
export async function getJournalEntries(
  days: number = 7
): Promise<LivingAgentJournalEntry[]> {
  const client = getClient();
  return client.get<LivingAgentJournalEntry[]>(
    `${PREFIX}/journal?days=${days}`
  );
}

/** Get tracked skills */
export async function getSkills(params?: {
  status?: string;
  domain?: string;
}): Promise<LivingAgentSkill[]> {
  const client = getClient();
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.domain) query.set("domain", params.domain);
  const qs = query.toString();
  return client.get<LivingAgentSkill[]>(
    `${PREFIX}/skills${qs ? `?${qs}` : ""}`
  );
}

/** Get heartbeat scheduler info */
export async function getHeartbeatInfo(): Promise<LivingAgentHeartbeat> {
  const client = getClient();
  return client.get<LivingAgentHeartbeat>(`${PREFIX}/heartbeat`);
}

/** Manually trigger a heartbeat cycle */
export async function triggerHeartbeat(): Promise<HeartbeatTriggerResult> {
  const client = getClient();
  return client.post<HeartbeatTriggerResult>(`${PREFIX}/heartbeat/trigger`);
}
