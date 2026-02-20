/**
 * User Profile API — Sprint 158.
 * Wraps GET/PATCH /users/me, GET/DELETE /users/me/identities.
 */
import { getClient } from "./client";
import type { UserProfile, UserIdentity } from "./types";

/** Fetch current user profile. */
export async function fetchProfile(): Promise<UserProfile> {
  return getClient().get<UserProfile>("/api/v1/users/me");
}

/** Update current user profile (name, avatar_url). */
export async function updateProfile(
  updates: { name?: string; avatar_url?: string }
): Promise<UserProfile> {
  return getClient().patch<UserProfile>("/api/v1/users/me", updates);
}

/** Fetch linked provider identities. */
export async function fetchIdentities(): Promise<UserIdentity[]> {
  return getClient().get<UserIdentity[]>("/api/v1/users/me/identities");
}

/** Unlink a provider identity (must keep >= 1). */
export async function unlinkIdentity(
  identityId: string
): Promise<{ status: string; identity_id: string }> {
  return getClient().delete<{ status: string; identity_id: string }>(
    `/api/v1/users/me/identities/${identityId}`
  );
}
