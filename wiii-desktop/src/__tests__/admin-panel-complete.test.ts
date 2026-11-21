/** Sprint 180: "Quan Tri Hoan Thien" — Complete Admin Panel tests */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAdminStore } from "@/stores/admin-store";

// ---------------------------------------------------------------------------
// Mock setup
// ---------------------------------------------------------------------------

vi.mock("@/api/client", () => ({
  getClient: vi.fn(() => ({
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  })),
}));

vi.mock("@/api/admin", () => ({
  getAdminDashboard: vi.fn(),
  searchAdminUsers: vi.fn().mockResolvedValue({ users: [], total: 0, limit: 20, offset: 0 }),
  getFeatureFlags: vi.fn().mockResolvedValue([]),
  toggleFeatureFlag: vi.fn(),
  deleteFeatureFlagOverride: vi.fn(),
  getAnalyticsOverview: vi.fn(),
  getLlmUsageAnalytics: vi.fn(),
  getUserAnalytics: vi.fn(),
  getAuditLogs: vi.fn().mockResolvedValue({ entries: [], total: 0, limit: 20, offset: 0 }),
  getAuthEvents: vi.fn().mockResolvedValue({ entries: [], total: 0, limit: 20, offset: 0 }),
  gdprExportUser: vi.fn(),
  gdprForgetUser: vi.fn(),
  getAdminOrgDetail: vi.fn(),
  getAdminOrgMembers: vi.fn().mockResolvedValue([]),
  deactivateUser: vi.fn(),
  reactivateUser: vi.fn(),
  changeUserRole: vi.fn(),
  changeUserPlatformRole: vi.fn(),
  addOrgMember: vi.fn(),
  removeOrgMember: vi.fn(),
}));

// Reset store before each test
beforeEach(() => {
  useAdminStore.getState().reset();
  vi.clearAllMocks();
});

// =============================================================================
// GROUP 1: API Exports — verify Sprint 180 functions exist
// =============================================================================

describe("Sprint 180 API Exports", () => {
  it("exports deactivateUser as a function", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.deactivateUser).toBe("function");
  });

  it("exports reactivateUser as a function", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.reactivateUser).toBe("function");
  });

  it("exports changeUserRole as a function", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.changeUserRole).toBe("function");
  });

  it("exports changeUserPlatformRole as a function", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.changeUserPlatformRole).toBe("function");
  });

  it("exports addOrgMember as a function", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.addOrgMember).toBe("function");
  });

  it("exports removeOrgMember as a function", async () => {
    const api = await vi.importActual<typeof import("@/api/admin")>("@/api/admin");
    expect(typeof api.removeOrgMember).toBe("function");
  });
});

// =============================================================================
// GROUP 2: Store toast functionality
// =============================================================================

describe("Admin Store — Toast", () => {
  it("toast is initially null", () => {
    expect(useAdminStore.getState().toast).toBeNull();
  });

  it("showToast sets the toast state", () => {
    useAdminStore.getState().showToast("Test message", "success");
    const state = useAdminStore.getState();
    expect(state.toast).toEqual({ message: "Test message", type: "success" });
  });

  it("showToast auto-clears after timeout", () => {
    vi.useFakeTimers();
    try {
      useAdminStore.getState().showToast("Temporary message", "error");
      expect(useAdminStore.getState().toast).not.toBeNull();

      vi.advanceTimersByTime(3100);
      expect(useAdminStore.getState().toast).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

// =============================================================================
// GROUP 3: Store user actions (deactivate/reactivate/changeRole)
// =============================================================================

describe("Admin Store — User Actions", () => {
  let mockDeactivateUser: ReturnType<typeof vi.fn>;
  let mockReactivateUser: ReturnType<typeof vi.fn>;
  let mockChangeUserRole: ReturnType<typeof vi.fn>;
  let mockChangeUserPlatformRole: ReturnType<typeof vi.fn>;
  let mockSearchAdminUsers: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    const adminApi = await import("@/api/admin");
    mockDeactivateUser = adminApi.deactivateUser as unknown as ReturnType<typeof vi.fn>;
    mockReactivateUser = adminApi.reactivateUser as unknown as ReturnType<typeof vi.fn>;
    mockChangeUserRole = adminApi.changeUserRole as unknown as ReturnType<typeof vi.fn>;
    mockChangeUserPlatformRole = adminApi.changeUserPlatformRole as unknown as ReturnType<typeof vi.fn>;
    mockSearchAdminUsers = adminApi.searchAdminUsers as unknown as ReturnType<typeof vi.fn>;
  });

  it("deactivateUser success shows success toast and refreshes users", async () => {
    mockDeactivateUser.mockResolvedValueOnce({ id: "u1", is_active: false });
    mockSearchAdminUsers.mockResolvedValueOnce({ users: [], total: 0, limit: 20, offset: 0 });

    await useAdminStore.getState().deactivateUser("u1");

    expect(mockDeactivateUser).toHaveBeenCalledWith("u1");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    expect(toast!.message).toContain("vô hiệu hoá");
  });

  it("deactivateUser error shows error toast", async () => {
    mockDeactivateUser.mockRejectedValueOnce(new Error("Network error"));

    await useAdminStore.getState().deactivateUser("u1");

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
  });

  it("reactivateUser success shows success toast", async () => {
    mockReactivateUser.mockResolvedValueOnce({ id: "u2", is_active: true });
    mockSearchAdminUsers.mockResolvedValueOnce({ users: [], total: 0, limit: 20, offset: 0 });

    await useAdminStore.getState().reactivateUser("u2");

    expect(mockReactivateUser).toHaveBeenCalledWith("u2");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    expect(toast!.message).toContain("kích hoạt lại");
  });

  it("reactivateUser error shows error toast", async () => {
    mockReactivateUser.mockRejectedValueOnce(new Error("Forbidden"));

    await useAdminStore.getState().reactivateUser("u2");

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
  });

  it("changeUserPlatformRole success shows toast with account type label", async () => {
    mockChangeUserPlatformRole.mockResolvedValueOnce({
      id: "u3",
      role: "admin",
      platform_role: "platform_admin",
    });
    mockSearchAdminUsers.mockResolvedValueOnce({ users: [], total: 0, limit: 20, offset: 0 });

    await useAdminStore.getState().changeUserPlatformRole("u3", "platform_admin");

    expect(mockChangeUserPlatformRole).toHaveBeenCalledWith("u3", "platform_admin");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    expect(toast!.message).toContain("Platform Admin");
  });

  it("changeUserPlatformRole error shows error toast", async () => {
    mockChangeUserPlatformRole.mockRejectedValueOnce(new Error("Unauthorized"));

    await useAdminStore.getState().changeUserPlatformRole("u3", "platform_admin");

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
  });
});

// =============================================================================
// GROUP 4: Store org member actions (add/remove)
// =============================================================================

describe("Admin Store — Org Member Actions", () => {
  let mockAddOrgMember: ReturnType<typeof vi.fn>;
  let mockRemoveOrgMember: ReturnType<typeof vi.fn>;
  let mockGetAdminOrgMembers: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    const adminApi = await import("@/api/admin");
    mockAddOrgMember = adminApi.addOrgMember as unknown as ReturnType<typeof vi.fn>;
    mockRemoveOrgMember = adminApi.removeOrgMember as unknown as ReturnType<typeof vi.fn>;
    mockGetAdminOrgMembers = adminApi.getAdminOrgMembers as unknown as ReturnType<typeof vi.fn>;
  });

  it("addOrgMember success shows toast 'Da them thanh vien'", async () => {
    mockAddOrgMember.mockResolvedValueOnce(undefined);
    mockGetAdminOrgMembers.mockResolvedValueOnce([]);

    await useAdminStore.getState().addOrgMember("org-1", "user-1", "student");

    expect(mockAddOrgMember).toHaveBeenCalledWith("org-1", "user-1", "student");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    expect(toast!.message).toBe("Đã thêm thành viên");
  });

  it("addOrgMember error shows error toast", async () => {
    mockAddOrgMember.mockRejectedValueOnce(new Error("User not found"));

    await useAdminStore.getState().addOrgMember("org-1", "invalid-user");

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
  });

  it("removeOrgMember success shows toast 'Da xoa thanh vien'", async () => {
    mockRemoveOrgMember.mockResolvedValueOnce(undefined);
    mockGetAdminOrgMembers.mockResolvedValueOnce([]);

    await useAdminStore.getState().removeOrgMember("org-1", "user-2");

    expect(mockRemoveOrgMember).toHaveBeenCalledWith("org-1", "user-2");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    expect(toast!.message).toBe("Đã xoá thành viên");
  });

  it("removeOrgMember error shows error toast", async () => {
    mockRemoveOrgMember.mockRejectedValueOnce(new Error("Permission denied"));

    await useAdminStore.getState().removeOrgMember("org-1", "user-2");

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
  });
});

// =============================================================================
// GROUP 7: Org member management logic
// =============================================================================

describe("Admin Store — Member Refresh", () => {

  it("store refreshes org members after add/remove action", async () => {
    const adminApi = await import("@/api/admin");
    const mockAddOrgMember = adminApi.addOrgMember as unknown as ReturnType<typeof vi.fn>;
    const mockGetAdminOrgMembers = adminApi.getAdminOrgMembers as unknown as ReturnType<typeof vi.fn>;

    mockAddOrgMember.mockResolvedValueOnce(undefined);
    mockGetAdminOrgMembers.mockResolvedValueOnce([
      { user_id: "user-new", role: "student", joined_at: "2026-02-23" },
    ]);

    await useAdminStore.getState().addOrgMember("org-1", "user-new", "student");

    // fetchOrgMembers should have been triggered (via getAdminOrgMembers)
    expect(mockGetAdminOrgMembers).toHaveBeenCalledWith("org-1");
  });
});

// =============================================================================
// GROUP 8: Store toast lifecycle
// =============================================================================

describe("Admin Store — Toast Lifecycle", () => {
  it("success toast has green styling (type check)", () => {
    useAdminStore.getState().showToast("Success!", "success");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    // Component uses isSuccess = toast.type === "success" to apply green classes
    const isSuccess = toast!.type === "success";
    expect(isSuccess).toBe(true);
  });

  it("error toast has red styling (type check)", () => {
    useAdminStore.getState().showToast("Error!", "error");
    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
    const isSuccess = toast!.type === "success";
    expect(isSuccess).toBe(false);
  });

  it("auto-dismiss clears toast after 3 seconds", () => {
    vi.useFakeTimers();
    try {
      useAdminStore.getState().showToast("Auto dismiss", "success");
      expect(useAdminStore.getState().toast).not.toBeNull();

      // Not yet cleared at 2.9s
      vi.advanceTimersByTime(2900);
      expect(useAdminStore.getState().toast).not.toBeNull();

      // Cleared after 3s+
      vi.advanceTimersByTime(200);
      expect(useAdminStore.getState().toast).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});

// =============================================================================
// GROUP 9: toggleFlag shows toast (Sprint 180 enhancement)
// =============================================================================

describe("Admin Store — toggleFlag Toast", () => {
  let mockToggleFeatureFlag: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    const adminApi = await import("@/api/admin");
    mockToggleFeatureFlag = adminApi.toggleFeatureFlag as unknown as ReturnType<typeof vi.fn>;
  });

  it("toggleFlag success shows success toast with flag key", async () => {
    mockToggleFeatureFlag.mockResolvedValueOnce({
      key: "enable_mcp_server",
      value: true,
      source: "db_override",
      flag_type: "release",
      description: null,
      owner: null,
      expires_at: null,
    });

    useAdminStore.setState({
      featureFlags: [
        { key: "enable_mcp_server", value: false, source: "config", flag_type: "release", description: null, owner: null, expires_at: null },
      ],
    });

    await useAdminStore.getState().toggleFlag("enable_mcp_server", true);

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("success");
    expect(toast!.message).toContain("enable_mcp_server");
  });

  it("toggleFlag error shows error toast", async () => {
    mockToggleFeatureFlag.mockRejectedValueOnce(new Error("Server error"));

    await useAdminStore.getState().toggleFlag("enable_mcp_server", true);

    const toast = useAdminStore.getState().toast;
    expect(toast).not.toBeNull();
    expect(toast!.type).toBe("error");
  });
});

describe("Admin Store - Host Action Timeline", () => {
  it("fetchHostActionEvents queries auth events with host_action provider", async () => {
    const adminApi = await import("@/api/admin");
    const mockGetAuthEvents = adminApi.getAuthEvents as unknown as ReturnType<typeof vi.fn>;
    mockGetAuthEvents.mockResolvedValueOnce({
      entries: [
        {
          id: "host-1",
          event_type: "host_action.preview_created",
          user_id: "teacher-1",
          provider: "host_action",
          result: "success",
          reason: null,
          ip_address: "127.0.0.1",
          organization_id: "org-1",
          metadata: { summary: "Lesson patch preview ready." },
          created_at: "2026-03-23T10:00:00Z",
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });

    await useAdminStore.getState().fetchHostActionEvents(0);

    expect(mockGetAuthEvents).toHaveBeenCalledWith({
      provider: "host_action",
      limit: 20,
      offset: 0,
    });
    expect(useAdminStore.getState().hostActionEvents).toHaveLength(1);
  });
});
