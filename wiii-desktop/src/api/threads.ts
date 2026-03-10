/**
 * Threads API module — cross-platform conversation sync.
 *
 * Sprint 225: Server-side thread listing + message history retrieval
 * for syncing conversations across LMS embed, desktop, and web clients.
 */
import { getClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ThreadView {
  thread_id: string;
  user_id: string;
  domain_id: string;
  title: string | null;
  message_count: number;
  last_message_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  extra_data: Record<string, unknown>;
}

export interface ThreadListResponse {
  status: string;
  threads: ThreadView[];
  total: number;
}

export interface ThreadMessage {
  id: string;
  role: string;
  content: string;
  created_at: string | null;
}

export interface ThreadMessagesResponse {
  status: string;
  messages: ThreadMessage[];
  total: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Fetch the user's conversation list from the server. */
export async function fetchThreads(
  limit = 50,
  offset = 0,
): Promise<ThreadListResponse> {
  const client = getClient();
  return client.get<ThreadListResponse>("/api/v1/threads", {
    limit: String(limit),
    offset: String(offset),
  });
}

/** Fetch message history for a specific thread. */
export async function fetchThreadMessages(
  threadId: string,
  limit = 100,
): Promise<ThreadMessage[]> {
  const client = getClient();
  const resp = await client.get<ThreadMessagesResponse>(
    `/api/v1/threads/${encodeURIComponent(threadId)}/messages`,
    { limit: String(limit) },
  );
  return resp.messages ?? [];
}

/** Delete a server-side thread (fire-and-forget). */
export async function deleteServerThread(threadId: string): Promise<void> {
  const client = getClient();
  await client.delete<unknown>(`/api/v1/threads/${encodeURIComponent(threadId)}`);
}

/** Rename a server-side thread (fire-and-forget). */
export async function renameServerThread(
  threadId: string,
  title: string,
): Promise<void> {
  const client = getClient();
  await client.patch<unknown>(`/api/v1/threads/${encodeURIComponent(threadId)}/title`, {
    title,
  });
}
