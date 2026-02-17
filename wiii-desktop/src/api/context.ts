/**
 * Context management API — Sprint 80.
 * Wraps GET /context/info, POST /context/compact, POST /context/clear.
 */
import { getClient } from "./client";
import type {
  ContextInfoResponse,
  CompactResponse,
  ClearContextResponse,
} from "./types";

/** Fetch context utilization info for a session. */
export async function fetchContextInfo(
  sessionId: string
): Promise<ContextInfoResponse> {
  return getClient().getWithHeaders<ContextInfoResponse>(
    "/api/v1/context/info",
    { "X-Session-ID": sessionId }
  );
}

/** Trigger context compaction (summarize old messages). */
export async function compactContext(
  sessionId: string
): Promise<CompactResponse> {
  return getClient().postWithHeaders<CompactResponse>(
    "/api/v1/context/compact",
    {},
    { "X-Session-ID": sessionId }
  );
}

/** Clear conversation context for a session. */
export async function clearContext(
  sessionId: string
): Promise<ClearContextResponse> {
  return getClient().postWithHeaders<ClearContextResponse>(
    "/api/v1/context/clear",
    {},
    { "X-Session-ID": sessionId }
  );
}
