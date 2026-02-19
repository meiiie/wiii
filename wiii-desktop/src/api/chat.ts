/**
 * Chat API module — sendMessage (SSE streaming), thread management
 */
import type {
  ChatRequest,
  ChatResponse,
  ThreadListResponse,
  ThreadView,
  ThreadActionResponse,
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
): Promise<SSEStreamResult> {
  const client = getClient();
  const extraHeaders: Record<string, string> = {};
  if (lastEventId) {
    extraHeaders["Last-Event-ID"] = lastEventId;
  }
  // Sprint 153b: Pass abort signal to postStream so initial HTTP request is also cancellable
  const stream = await client.postStream("/api/v1/chat/stream/v3", request, extraHeaders, abortSignal);
  return parseSSEStream(stream, handlers, abortSignal);
}

/**
 * Send a chat message synchronously (non-streaming).
 * Uses /chat endpoint — returns complete response.
 */
export async function sendMessageSync(
  request: ChatRequest
): Promise<ChatResponse> {
  const client = getClient();
  return client.post<ChatResponse>("/api/v1/chat", request);
}

// =============================================================================
// Thread Management API (Sprint 16: Server-side conversation index)
// =============================================================================

/**
 * List all conversation threads for the authenticated user.
 * Server-side conversation index — used for multi-device sync.
 */
export async function listThreads(
  limit = 50,
  offset = 0
): Promise<ThreadListResponse> {
  const client = getClient();
  return client.get<ThreadListResponse>("/api/v1/threads", {
    limit: String(limit),
    offset: String(offset),
  });
}

/**
 * Get a specific thread by ID.
 */
export async function getThread(threadId: string): Promise<ThreadView> {
  const client = getClient();
  return client.get<ThreadView>(`/api/v1/threads/${encodeURIComponent(threadId)}`);
}

/**
 * Delete (soft-delete) a thread.
 */
export async function deleteThread(
  threadId: string
): Promise<ThreadActionResponse> {
  const client = getClient();
  return client.delete<ThreadActionResponse>(
    `/api/v1/threads/${encodeURIComponent(threadId)}`
  );
}

/**
 * Rename a thread.
 */
export async function renameThread(
  threadId: string,
  title: string
): Promise<ThreadActionResponse> {
  const client = getClient();
  return client.patch<ThreadActionResponse>(
    `/api/v1/threads/${encodeURIComponent(threadId)}/title`,
    { title }
  );
}
