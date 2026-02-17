/**
 * User Preferences API — Sprint 120.
 * Wraps GET/PUT /preferences for learning style, difficulty, pronoun style.
 */
import { getClient } from "./client";
import type { UserPreferences, UserPreferencesUpdate } from "./types";

/** Fetch user preferences. */
export async function fetchPreferences(): Promise<UserPreferences> {
  return getClient().get<UserPreferences>("/api/v1/preferences");
}

/** Update user preferences (partial update). */
export async function updatePreferences(
  updates: UserPreferencesUpdate
): Promise<UserPreferences> {
  return getClient().put<UserPreferences>("/api/v1/preferences", updates);
}
