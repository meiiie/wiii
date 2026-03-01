/**
 * Soul Bridge API client — fetches peer status and events from Wiii backend.
 * Sprint 216: SoulBridgePanel data layer.
 */
import { getClient } from "./client";

// ── Types ──

export interface SoulBridgePeer {
  state: "CONNECTED" | "CONNECTING" | "RECONNECTING" | "DISCONNECTED";
  url?: string;
  has_card: boolean;
}

export interface SoulBridgeStatus {
  initialized: boolean;
  soul_id: string;
  bridge_events: string[];
  peer_count: number;
  peers: Record<string, SoulBridgePeer>;
}

export interface AgentCard {
  name: string;
  description: string;
  capabilities: string[];
  supported_events: string[];
  soul_id?: string;
}

export interface PeerEvent {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  priority: string;
  timestamp: string;
  source_soul: string;
}

export interface PeerDetail {
  peer_id: string;
  state: string;
  card: AgentCard | null;
  latest_status: Record<string, unknown> | null;
  recent_events: PeerEvent[];
  event_count: number;
}

// ── API Calls ──

const PREFIX = "/api/v1/soul-bridge";

/** Get overall bridge status including all peer connection states */
export async function getSoulBridgeStatus(): Promise<SoulBridgeStatus> {
  const client = getClient();
  return client.get<SoulBridgeStatus>(`${PREFIX}/status`);
}

/** Get detailed peer info: card + state + recent events */
export async function getPeerDetail(peerId: string): Promise<PeerDetail> {
  const client = getClient();
  return client.get<PeerDetail>(`${PREFIX}/peers/${peerId}/detail`);
}

/** Get recent events from a specific peer */
export async function getPeerEvents(
  peerId: string,
  params?: { limit?: number; event_type?: string }
): Promise<{ peer_id: string; events: PeerEvent[]; count: number }> {
  const client = getClient();
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.event_type) query.set("event_type", params.event_type);
  const qs = query.toString();
  return client.get(`${PREFIX}/peers/${peerId}/events${qs ? `?${qs}` : ""}`);
}
