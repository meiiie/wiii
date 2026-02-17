/**
 * Character State API — Sprint 120.
 * Wraps GET /character/state to fetch Wiii's personality blocks.
 */
import { getClient } from "./client";
import type { CharacterStateResponse } from "./types";

/** Fetch Wiii's current character state (all blocks). */
export async function fetchCharacterState(): Promise<CharacterStateResponse> {
  return getClient().get<CharacterStateResponse>("/api/v1/character/state");
}
