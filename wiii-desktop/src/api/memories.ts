/**
 * Memory management API — Sprint 80.
 * Wraps GET /memories/{user_id}, DELETE /memories/{user_id}/{memory_id},
 * DELETE /memories/{user_id} (bulk clear).
 */
import { getClient } from "./client";
import type { MemoryListResponse, DeleteMemoryResponse, ClearMemoriesResponse } from "./types";

/** Fetch all memories for a user. */
export async function fetchMemories(
  userId: string
): Promise<MemoryListResponse> {
  return getClient().get<MemoryListResponse>(`/api/v1/memories/${userId}`);
}

/** Delete a single memory by ID. */
export async function deleteMemory(
  userId: string,
  memoryId: string
): Promise<DeleteMemoryResponse> {
  return getClient().delete<DeleteMemoryResponse>(
    `/api/v1/memories/${userId}/${memoryId}`
  );
}

/** Clear ALL memories for a user (bulk delete). */
export async function clearMemories(
  userId: string
): Promise<ClearMemoriesResponse> {
  return getClient().delete<ClearMemoriesResponse>(
    `/api/v1/memories/${userId}`
  );
}
