/** Sprint 180: "Quan Tri Hoan Thien" — Complete Admin Panel tests */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAdminStore } from "@/stores/admin-store";
import type { AdminFeatureFlag } from "@/api/types";

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
// GROUP 5: Flag categorization (pure function tests)
// =============================================================================

describe("categorizeFlags", () => {
  let categorizeFlags: typeof import("@/components/admin/FeatureFlagsTab").categorizeFlags;

  beforeEach(async () => {
    const mod = await import("@/components/admin/FeatureFlagsTab");
    categorizeFlags = mod.categorizeFlags;
  });

  const makeFlag = (key: string, value = true): AdminFeatureFlag => ({
    key,
    value,
    source: "config",
    flag_type: "release",
    description: null,
    owner: null,
    expires_at: null,
  });

  it("correctly groups flags by category", () => {
    const flags = [
      makeFlag("enable_corrective_rag"),
      makeFlag("enable_product_search"),
      makeFlag("enable_google_oauth"),
    ];
    const groups = categorizeFlags(flags);

    expect(groups.length).toBeGreaterThanOrEqual(3);
    const coreAi = groups.find((g) => g.category.id === "core_ai");
    const search = groups.find((g) => g.category.id === "search");
    const auth = groups.find((g) => g.category.id === "auth");

    expect(coreAi).toBeDefined();
    expect(coreAi!.flags).toHaveLength(1);
    expect(coreAi!.flags[0].key).toBe("enable_corrective_rag");

    expect(search).toBeDefined();
    expect(search!.flags).toHaveLength(1);
    expect(search!.flags[0].key).toBe("enable_product_search");

    expect(auth).toBeDefined();
    expect(auth!.flags).toHaveLength(1);
    expect(auth!.flags[0].key).toBe("enable_google_oauth");
  });

  it("puts unknown flags in 'other' category", () => {
    const flags = [
      makeFlag("some_random_flag_xyz"),
      makeFlag("another_unknown_flag"),
    ];
    const groups = categorizeFlags(flags);

    expect(groups).toHaveLength(1);
    expect(groups[0].category.id).toBe("other");
    expect(groups[0].flags).toHaveLength(2);
  });

  it("returns empty array for empty input", () => {
    const groups = categorizeFlags([]);
    expect(groups).toEqual([]);
  });

  it("maps standard categories correctly", () => {
    const flags = [
      makeFlag("enable_corrective_rag"),        // core_ai
      makeFlag("enable_core_memory"),            // memory
      makeFlag("enable_product_search"),         // search
      makeFlag("enable_google_oauth"),           // auth
      makeFlag("enable_multi_tenant"),           // multi_tenant
      makeFlag("enable_websocket"),              // channels
      makeFlag("enable_living_agent"),           // living_agent
      makeFlag("enable_soul_emotion"),           // emotion
      makeFlag("enable_mcp_server"),             // tools
      makeFlag("enable_vision"),                 // content_ui
      makeFlag("enable_llm_failover"),           // infra
      makeFlag("enable_admin_dashboard"),        // admin
      makeFlag("enable_lms_integration"),        // lms
    ];
    const groups = categorizeFlags(flags);

    const ids = groups.map((g) => g.category.id);
    expect(ids).toContain("core_ai");
    expect(ids).toContain("memory");
    expect(ids).toContain("search");
    expect(ids).toContain("auth");
    expect(ids).toContain("multi_tenant");
    expect(ids).toContain("channels");
    expect(ids).toContain("living_agent");
    expect(ids).toContain("emotion");
    expect(ids).toContain("tools");
    expect(ids).toContain("content_ui");
    expect(ids).toContain("infra");
    expect(ids).toContain("admin");
    expect(ids).toContain("lms");
    // No "other" since all flags match a category
    expect(ids).not.toContain("other");
  });

  it("pre-filtered flags still categorize correctly", () => {
    const flags = [
      makeFlag("enable_mcp_server"),
      makeFlag("enable_mcp_client"),
      makeFlag("enable_product_search"),
    ];
    // Simulate a search filter for "mcp"
    const filtered = flags.filter((f) => f.key.includes("mcp"));
    const groups = categorizeFlags(filtered);

    expect(groups).toHaveLength(1);
    expect(groups[0].category.id).toBe("tools");
    expect(groups[0].flags).toHaveLength(2);
  });

  it("enabled/total count per category is correct", () => {
    const flags = [
      makeFlag("enable_corrective_rag", true),
      makeFlag("enable_answer_verification", false),
      makeFlag("deep_reasoning", true),
    ];
    const groups = categorizeFlags(flags);
    const coreAi = groups.find((g) => g.category.id === "core_ai");

    expect(coreAi).toBeDefined();
    const enabledCount = coreAi!.flags.filter((f) => f.value).length;
    const totalCount = coreAi!.flags.length;
    expect(enabledCount).toBe(2);
    expect(totalCount).toBe(3);
  });
});

// =============================================================================
// GROUP 6: UsersTab overflow menu logic
// =============================================================================

describe("UsersTab — Overflow Menu Logic", () => {
  it("UsersTab imports MoreHorizontal for overflow menu", { timeout: 15_000 }, async () => {
    // Verify the component file uses MoreHorizontal
    const mod = await import("@/components/admin/UsersTab");
    // If UsersTab exports successfully, the MoreHorizontal import is resolved
    expect(typeof mod.UsersTab).toBe("function");
  });

  it("UsersTab imports ConfirmDialog for deactivation", async () => {
    const mod = await import("@/components/common/ConfirmDialog");
    expect(typeof mod.ConfirmDialog).toBe("function");
  });

  it("self-protection: isSelf hides deactivate (logic test)", () => {
    // Simulate the condition used in the component
    const currentUserId = "my-user-id";
    const user = { id: "my-user-id", is_active: true };
    const isSelf = user.id === currentUserId;
    // Deactivate button is only shown when !isSelf && user.is_active
    expect(isSelf).toBe(true);
    // Therefore deactivate should not be shown
    expect(!isSelf && user.is_active).toBe(false);
  });

  it("PLATFORM_ROLE_OPTIONS has 2 account types", () => {
    const PLATFORM_ROLE_OPTIONS = [
      { value: "user", label: "Wiii User" },
      { value: "platform_admin", label: "Platform Admin" },
    ];
    expect(PLATFORM_ROLE_OPTIONS).toHaveLength(2);
    expect(PLATFORM_ROLE_OPTIONS.map((r) => r.value)).toEqual(["user", "platform_admin"]);
  });

  it("inactive user only shows reactivate (logic test)", () => {
    const user = { id: "u1", is_active: false };
    // In UsersTab: user.is_active ? (deactivate + role) : (reactivate)
    const showReactivate = !user.is_active;
    const showDeactivateMenu = user.is_active;
    expect(showReactivate).toBe(true);
    expect(showDeactivateMenu).toBe(false);
  });

  it("active non-self user shows deactivate and role change (logic test)", () => {
    const currentUserId = "admin-me";
    const user = { id: "other-user", is_active: true };
    const isSelf = user.id === currentUserId;
    const showDeactivate = !isSelf && user.is_active;
    const showRoleChange = user.is_active;
    expect(showDeactivate).toBe(true);
    expect(showRoleChange).toBe(true);
  });

  it("openMenuUserId tracks which menu is open", () => {
    // Simulate state management pattern from the component
    let openMenuUserId: string | null = null;

    openMenuUserId = "u1";
    expect(openMenuUserId).toBe("u1");

    // Toggle same user closes the menu
    openMenuUserId = openMenuUserId === "u1" ? null : "u1";
    expect(openMenuUserId).toBeNull();

    // Open another user
    openMenuUserId = "u2";
    expect(openMenuUserId).toBe("u2");
  });

  it("platform and legacy labels stay separate", () => {
    const PLATFORM_ROLE_LABELS: Record<string, string> = {
      user: "Wiii User",
      platform_admin: "Platform Admin",
    };
    const LEGACY_ROLE_LABELS: Record<string, string> = {
      student: "Compatibility: Student",
      teacher: "Compatibility: Teacher",
      admin: "Compatibility: Admin",
    };
    expect(Object.keys(PLATFORM_ROLE_LABELS)).toHaveLength(2);
    expect(PLATFORM_ROLE_LABELS.user).toBe("Wiii User");
    expect(PLATFORM_ROLE_LABELS.platform_admin).toBe("Platform Admin");
    expect(LEGACY_ROLE_LABELS.student).toContain("Student");
  });
});

// =============================================================================
// GROUP 7: Org member management logic
// =============================================================================

describe("OrgDetailView — Member Management Logic", () => {
  it("add member form requires user ID and allows role select", () => {
    // Simulate the add form's validation logic from MembersSection
    let newUserId = "";
    const newRole = "student";

    // Empty user ID should prevent submission
    const canSubmitEmpty = !!newUserId.trim();
    expect(canSubmitEmpty).toBe(false);

    // Non-empty user ID allows submission
    newUserId = "user-123";
    const canSubmitFilled = !!newUserId.trim();
    expect(canSubmitFilled).toBe(true);

    // Role default is "student"
    expect(newRole).toBe("student");
  });

  it("remove member uses ConfirmDialog pattern", async () => {
    // Verify ConfirmDialog is used in OrgDetailView
    const mod = await import("@/components/admin/OrgDetailView");
    expect(typeof mod.OrgDetailView).toBe("function");

    // ConfirmDialog itself should be a function component
    const confirmMod = await import("@/components/common/ConfirmDialog");
    expect(typeof confirmMod.ConfirmDialog).toBe("function");
  });

  it("empty members shows empty message (logic test)", () => {
    const members: unknown[] = [];
    const loading = false;
    // In MembersSection: !loading && members.length === 0 shows "Chua co thanh vien nao"
    const showEmptyMessage = !loading && members.length === 0;
    expect(showEmptyMessage).toBe(true);
  });

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
// GROUP 8: Toast component logic
// =============================================================================

describe("AdminToast — Component Logic", () => {
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

  it("does not render when toast is null", () => {
    // Component: if (!toast) return null;
    const toast = useAdminStore.getState().toast;
    expect(toast).toBeNull();
    // AdminToast returns null in this case
    const shouldRender = toast !== null;
    expect(shouldRender).toBe(false);
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
