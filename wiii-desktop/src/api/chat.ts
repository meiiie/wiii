/**
 * Chat API module — sendMessage (SSE streaming), thread management
 */
import type {
  ChatRequest,
} from "./types";
import { parseSSEStream, type SSEEventHandler, type SSEStreamResult } from "./sse";
import { getClient } from "./client";

/**
 * Send a chat message with SSE streaming (v3).
 * This is the primary chat method — uses /chat/stream/v3.
 *
 * @param lastEventId - Optional Last-Event-ID for SSE reconnection
 * @returns SSEStreamResult with lastEventId for potential reconnection
 */
export async function sendMessageStream(
  request: ChatRequest,
  handlers: SSEEventHandler,
  abortSignal?: AbortSignal,
  lastEventId?: string | null,
  requestId?: string | null,
): Promise<SSEStreamResult> {
  const client = getClient();
  const extraHeaders: Record<string, string> = {};
  if (lastEventId) {
    extraHeaders["Last-Event-ID"] = lastEventId;
  }
  if (requestId) {
    extraHeaders["X-Request-ID"] = requestId;
  }
  // Sprint 153b: Pass abort signal to postStream so initial HTTP request is also cancellable
  const stream = await client.postStream("/api/v1/chat/stream/v3", request, extraHeaders, abortSignal);
  return parseSSEStream(stream, handlers, abortSignal);
}

