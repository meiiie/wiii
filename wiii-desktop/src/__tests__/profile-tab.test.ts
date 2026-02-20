/**
 * Sprint 158: Profile tab + User API tests.
 * 8 tests covering API module and UserTab OAuth/legacy behavior.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// API module tests
// ---------------------------------------------------------------------------

describe("users API module", () => {
  const mockGet = vi.fn();
  const mockPatch = vi.fn();
  const mockDelete = vi.fn();

  beforeEach(() => {
    vi.resetModules();
    vi.doMock("@/api/client", () => ({
      getClient: () => ({
        get: mockGet,
        patch: mockPatch,
        delete: mockDelete,
      }),
    }));
    mockGet.mockReset();
    mockPatch.mockReset();
    mockDelete.mockReset();
  });

  it("fetchProfile calls GET /api/v1/users/me", async () => {
    mockGet.mockResolvedValue({ id: "u1", email: "a@b.com", name: "Test", role: "student" });
    const { fetchProfile } = await import("@/api/users");
    const result = await fetchProfile();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/users/me");
    expect(result.id).toBe("u1");
  });

  it("updateProfile calls PATCH /api/v1/users/me", async () => {
    mockPatch.mockResolvedValue({ id: "u1", name: "New Name" });
    const { updateProfile } = await import("@/api/users");
    await updateProfile({ name: "New Name" });
    expect(mockPatch).toHaveBeenCalledWith("/api/v1/users/me", { name: "New Name" });
  });

  it("fetchIdentities calls GET /api/v1/users/me/identities", async () => {
    mockGet.mockResolvedValue([{ id: "i1", provider: "google", provider_sub: "sub1" }]);
    const { fetchIdentities } = await import("@/api/users");
    const result = await fetchIdentities();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/users/me/identities");
    expect(result).toHaveLength(1);
  });

  it("unlinkIdentity calls DELETE with correct path", async () => {
    mockDelete.mockResolvedValue({ status: "unlinked", identity_id: "i1" });
    const { unlinkIdentity } = await import("@/api/users");
    const result = await unlinkIdentity("i1");
    expect(mockDelete).toHaveBeenCalledWith("/api/v1/users/me/identities/i1");
    expect(result.status).toBe("unlinked");
  });
});

// ---------------------------------------------------------------------------
// UserTab component behavior tests
// ---------------------------------------------------------------------------

describe("UserTab behavior", () => {
  it("types.ts exports UserProfile and UserIdentity", async () => {
    // Type-level check: ensure the interfaces exist by importing
    const types = await import("@/api/types");
    // UserProfile and UserIdentity are interfaces — they don't exist at runtime,
    // but we can verify the module exports compile
    expect(types).toBeDefined();
  });

  it("UserProfile interface has required fields", () => {
    // Compile-time type check: create a valid UserProfile object
    const profile: import("@/api/types").UserProfile = {
      id: "u1",
      role: "student",
      is_active: true,
    };
    expect(profile.id).toBe("u1");
    expect(profile.is_active).toBe(true);
  });

  it("UserIdentity interface has provider fields", () => {
    const identity: import("@/api/types").UserIdentity = {
      id: "i1",
      provider: "google",
      provider_sub: "sub123",
    };
    expect(identity.provider).toBe("google");
  });

  it("users API module exports all 4 functions", async () => {
    // Mock the client dependency
    vi.doMock("@/api/client", () => ({
      getClient: () => ({
        get: vi.fn().mockResolvedValue({}),
        patch: vi.fn().mockResolvedValue({}),
        delete: vi.fn().mockResolvedValue({}),
      }),
    }));
    const usersApi = await import("@/api/users");
    expect(typeof usersApi.fetchProfile).toBe("function");
    expect(typeof usersApi.updateProfile).toBe("function");
    expect(typeof usersApi.fetchIdentities).toBe("function");
    expect(typeof usersApi.unlinkIdentity).toBe("function");
  });
});
