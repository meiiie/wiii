/**
 * Memory management API — Sprint 80.
 * Wraps GET /memories/{user_id}, DELETE /memories/{user_id}/{memory_id}.
 */
import { getClient } from "./client";
import type { MemoryListResponse, DeleteMemoryResponse } from "./types";

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
