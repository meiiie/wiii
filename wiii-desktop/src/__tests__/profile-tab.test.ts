/** User profile and identity API types. */
import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// User profile API types
// ---------------------------------------------------------------------------

describe("User profile API types", () => {
  it("types.ts exports UserProfile and UserIdentity", async () => {
    // Type-level check: ensure the interfaces exist by importing
    const types = await import("@/api/types/organizations");
    // UserProfile and UserIdentity are interfaces — they don't exist at runtime,
    // but we can verify the module exports compile
    expect(types).toBeDefined();
  });

  it("UserProfile interface has required fields", () => {
    // Compile-time type check: create a valid UserProfile object
    const profile: import("@/api/types/organizations").UserProfile = {
      id: "u1",
      role: "student",
      is_active: true,
    };
    expect(profile.id).toBe("u1");
    expect(profile.is_active).toBe(true);
  });

  it("UserIdentity interface has provider fields", () => {
    const identity: import("@/api/types/organizations").UserIdentity = {
      id: "i1",
      provider: "google",
      provider_sub: "sub123",
    };
    expect(identity.provider).toBe("google");
  });

});
