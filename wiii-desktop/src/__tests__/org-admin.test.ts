/**
 * Sprint 181: "Hai Tầng Quyền Lực" — Desktop Tests
 *
 * Tests for:
 *   - AdminContext type and API function
 *   - org-store: adminContext state, fetchAdminContext, isSystemAdmin, isOrgAdmin
 *   - ui-store: activeView, open/close actions
 *   - org-admin-store: tabs, members, toast
 *   - Sidebar visibility logic (Shield vs Building2)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock API dependencies for org-store
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgPermissions: vi.fn().mockRejectedValue(new Error("Not configured")),
  updateOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
}));

vi.mock("@/api/admin", () => ({
  getAdminContext: vi.fn().mockRejectedValue(new Error("Not configured")),
  getAdminOrgDetail: vi.fn().mockRejectedValue(new Error("Not configured")),
  getAdminOrgMembers: vi.fn().mockResolvedValue([]),
  addOrgMember: vi.fn().mockResolvedValue(undefined),
  removeOrgMember: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/org-branding", () => ({
  applyOrgBranding: vi.fn(),
  resetBranding: vi.fn(),
  DEFAULT_BRANDING: { chatbot_name: "Wiii", welcome_message: "Xin chào!" },
}));

vi.mock("@/lib/constants", () => ({
  PERSONAL_ORG_ID: "personal",
}));

import { useOrgStore } from "@/stores/org-store";
import { useUIStore } from "@/stores/ui-store";
import { useOrgAdminStore } from "@/stores/org-admin-store";
import type { AdminContext } from "@/api/types";

// ---------------------------------------------------------------------------
// 1. AdminContext Type Tests
// ---------------------------------------------------------------------------

describe("AdminContext type", () => {
  it("should have correct shape for system admin", () => {
    const ctx: AdminContext = {
      is_system_admin: true,
      is_org_admin: true,
      admin_org_ids: ["org-1"],
      enable_org_admin: true,
    };
    expect(ctx.is_system_admin).toBe(true);
    expect(ctx.admin_org_ids).toHaveLength(1);
  });

  it("should represent regular user", () => {
    const ctx: AdminContext = {
      is_system_admin: false,
      is_org_admin: false,
      admin_org_ids: [],
      enable_org_admin: true,
    };
    expect(ctx.is_system_admin).toBe(false);
    expect(ctx.is_org_admin).toBe(false);
    expect(ctx.admin_org_ids).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 2. API Function Tests
// ---------------------------------------------------------------------------

describe("getAdminContext API", () => {
  it("should be exported from admin module", async () => {
    const adminModule = await import("@/api/admin");
    expect(typeof adminModule.getAdminContext).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// 3. org-store Admin Context Tests
// ---------------------------------------------------------------------------

describe("org-store admin context", () => {
  beforeEach(() => {
    useOrgStore.setState({
      adminContext: null,
      organizations: [],
      activeOrgId: null,
      multiTenantEnabled: false,
      subdomainOrgId: null,
      orgSettings: null,
      permissions: [],
    });
  });

  it("should start with null adminContext", () => {
    expect(useOrgStore.getState().adminContext).toBeNull();
  });

  it("isSystemAdmin returns false when no context", () => {
    expect(useOrgStore.getState().isSystemAdmin()).toBe(false);
  });

  it("isOrgAdmin returns false when no context", () => {
    expect(useOrgStore.getState().isOrgAdmin()).toBe(false);
  });

  it("isSystemAdmin returns true when system admin", () => {
    useOrgStore.setState({
      adminContext: {
        is_system_admin: true,
        is_org_admin: true,
        admin_org_ids: [],
        enable_org_admin: true,
      },
    });
    expect(useOrgStore.getState().isSystemAdmin()).toBe(true);
  });

  it("isOrgAdmin returns true for specific org", () => {
    useOrgStore.setState({
      adminContext: {
        is_system_admin: false,
        is_org_admin: true,
        admin_org_ids: ["org-x", "org-y"],
        enable_org_admin: true,
      },
    });
    expect(useOrgStore.getState().isOrgAdmin("org-x")).toBe(true);
    expect(useOrgStore.getState().isOrgAdmin("org-z")).toBe(false);
  });

  it("isOrgAdmin returns true when any org admin (no orgId param)", () => {
    useOrgStore.setState({
      adminContext: {
        is_system_admin: false,
        is_org_admin: true,
        admin_org_ids: ["org-x"],
        enable_org_admin: true,
      },
    });
    expect(useOrgStore.getState().isOrgAdmin()).toBe(true);
  });

  it("isOrgAdmin returns false when enable_org_admin=false", () => {
    useOrgStore.setState({
      adminContext: {
        is_system_admin: false,
        is_org_admin: false,
        admin_org_ids: [],
        enable_org_admin: false,
      },
    });
    expect(useOrgStore.getState().isOrgAdmin()).toBe(false);
  });

  it("system admin is always org admin for any org", () => {
    useOrgStore.setState({
      adminContext: {
        is_system_admin: true,
        is_org_admin: true,
        admin_org_ids: [],
        enable_org_admin: true,
      },
    });
    expect(useOrgStore.getState().isOrgAdmin("any-org")).toBe(true);
  });

  it("isOrgAdmin false when admin_org_ids non-empty but enable_org_admin=false", () => {
    useOrgStore.setState({
      adminContext: {
        is_system_admin: false,
        is_org_admin: true,
        admin_org_ids: ["org-x"],
        enable_org_admin: false,
      },
    });
    expect(useOrgStore.getState().isOrgAdmin()).toBe(false);
  });

  it("fetchAdminContext sets context on success", async () => {
    const { getAdminContext } = await import("@/api/admin");
    (getAdminContext as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      is_system_admin: false,
      is_org_admin: true,
      admin_org_ids: ["org-test"],
      enable_org_admin: true,
    });

    await useOrgStore.getState().fetchAdminContext();
    const ctx = useOrgStore.getState().adminContext;
    expect(ctx).not.toBeNull();
    expect(ctx?.admin_org_ids).toEqual(["org-test"]);
  });

  it("fetchAdminContext sets null on error", async () => {
    const { getAdminContext } = await import("@/api/admin");
    (getAdminContext as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("Network"));

    await useOrgStore.getState().fetchAdminContext();
    expect(useOrgStore.getState().adminContext).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 4. ui-store Org Manager Panel Tests
// ---------------------------------------------------------------------------

describe("ui-store org manager panel", () => {
  beforeEach(() => {
    useUIStore.setState({
      activeView: "chat",
      orgManagerTargetOrgId: null,
      commandPaletteOpen: false,
    });
  });

  it("should start at chat with no orgId", () => {
    expect(useUIStore.getState().activeView).toBe("chat");
    expect(useUIStore.getState().orgManagerTargetOrgId).toBeNull();
  });

  it("openOrgManagerPanel sets activeView and orgId", () => {
    useUIStore.getState().openOrgManagerPanel("org-x");
    const state = useUIStore.getState();
    expect(state.activeView).toBe("org-admin");
    expect(state.orgManagerTargetOrgId).toBe("org-x");
  });

  it("closeOrgManagerPanel resets to chat", () => {
    useUIStore.getState().openOrgManagerPanel("org-x");
    useUIStore.getState().closeOrgManagerPanel();
    const state = useUIStore.getState();
    expect(state.activeView).toBe("chat");
    expect(state.orgManagerTargetOrgId).toBeNull();
  });

  it("openAdminPanel switches from org-admin to system-admin", () => {
    useUIStore.getState().openOrgManagerPanel("org-x");
    useUIStore.getState().openAdminPanel();
    expect(useUIStore.getState().activeView).toBe("system-admin");
  });

  it("closeAll returns to chat", () => {
    useUIStore.getState().openOrgManagerPanel("org-x");
    useUIStore.getState().closeAll();
    const state = useUIStore.getState();
    expect(state.activeView).toBe("chat");
    expect(state.orgManagerTargetOrgId).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 5. org-admin-store Tests
// ---------------------------------------------------------------------------

describe("org-admin-store", () => {
  beforeEach(() => {
    useOrgAdminStore.setState({
      activeTab: "dashboard",
      orgId: null,
      orgDetail: null,
      members: [],
      orgSettings: null,
      loading: false,
      toast: null,
    });
  });

  it("should start with dashboard tab", () => {
    expect(useOrgAdminStore.getState().activeTab).toBe("dashboard");
  });

  it("setActiveTab changes tab", () => {
    useOrgAdminStore.getState().setActiveTab("members");
    expect(useOrgAdminStore.getState().activeTab).toBe("members");
  });

  it("setOrgId sets org", () => {
    useOrgAdminStore.getState().setOrgId("org-x");
    expect(useOrgAdminStore.getState().orgId).toBe("org-x");
  });

  it("showToast sets and auto-clears toast", () => {
    vi.useFakeTimers();

    useOrgAdminStore.getState().showToast("success", "Done!");
    expect(useOrgAdminStore.getState().toast).toEqual({ type: "success", message: "Done!" });

    vi.advanceTimersByTime(3500);
    expect(useOrgAdminStore.getState().toast).toBeNull();

    vi.useRealTimers();
  });

  it("all 4 tab types are valid", () => {
    const tabs = ["dashboard", "members", "analytics", "settings"] as const;
    for (const tab of tabs) {
      useOrgAdminStore.getState().setActiveTab(tab);
      expect(useOrgAdminStore.getState().activeTab).toBe(tab);
    }
  });

  it("starts with empty members", () => {
    expect(useOrgAdminStore.getState().members).toEqual([]);
  });

  it("starts with null orgSettings", () => {
    expect(useOrgAdminStore.getState().orgSettings).toBeNull();
  });

  it("reset clears all state", () => {
    useOrgAdminStore.setState({
      activeTab: "members",
      orgId: "org-x",
      orgDetail: { id: "org-x", name: "Test" } as any,
      members: [{ user_id: "u1", role: "member" } as any],
      orgSettings: { branding: {} } as any,
      loading: true,
    });
    useOrgAdminStore.getState().reset();
    const state = useOrgAdminStore.getState();
    expect(state.activeTab).toBe("dashboard");
    expect(state.orgId).toBeNull();
    expect(state.orgDetail).toBeNull();
    expect(state.members).toEqual([]);
    expect(state.orgSettings).toBeNull();
    expect(state.loading).toBe(false);
    expect(state.toast).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 5b. org-admin-store Action Tests
// ---------------------------------------------------------------------------

describe("org-admin-store actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useOrgAdminStore.getState().reset();
  });

  it("fetchMembers populates members on success", async () => {
    const { getAdminOrgMembers } = await import("@/api/admin");
    (getAdminOrgMembers as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      { user_id: "u1", role: "member" },
      { user_id: "u2", role: "admin" },
    ]);

    await useOrgAdminStore.getState().fetchMembers("org-x");
    expect(useOrgAdminStore.getState().members).toHaveLength(2);
    expect(useOrgAdminStore.getState().loading).toBe(false);
  });

  it("fetchMembers handles error gracefully", async () => {
    const { getAdminOrgMembers } = await import("@/api/admin");
    (getAdminOrgMembers as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("Network"));

    await useOrgAdminStore.getState().fetchMembers("org-x");
    expect(useOrgAdminStore.getState().members).toEqual([]);
    expect(useOrgAdminStore.getState().loading).toBe(false);
  });

  it("addMember shows success toast and refetches", async () => {
    const { addOrgMember, getAdminOrgMembers } = await import("@/api/admin");
    (addOrgMember as ReturnType<typeof vi.fn>).mockResolvedValueOnce(undefined);
    (getAdminOrgMembers as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      { user_id: "new-user", role: "member" },
    ]);

    await useOrgAdminStore.getState().addMember("org-x", "new-user", "member");
    expect(useOrgAdminStore.getState().toast?.type).toBe("success");
  });

  it("addMember shows error toast on failure", async () => {
    const { addOrgMember } = await import("@/api/admin");
    (addOrgMember as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("403 Forbidden"));

    await useOrgAdminStore.getState().addMember("org-x", "new-user", "admin");
    expect(useOrgAdminStore.getState().toast?.type).toBe("error");
    expect(useOrgAdminStore.getState().toast?.message).toContain("403");
  });

  it("removeMember shows success toast and refetches", async () => {
    const { removeOrgMember, getAdminOrgMembers } = await import("@/api/admin");
    (removeOrgMember as ReturnType<typeof vi.fn>).mockResolvedValueOnce(undefined);
    (getAdminOrgMembers as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);

    await useOrgAdminStore.getState().removeMember("org-x", "user-1");
    expect(useOrgAdminStore.getState().toast?.type).toBe("success");
  });

  it("removeMember shows error toast on failure", async () => {
    const { removeOrgMember } = await import("@/api/admin");
    (removeOrgMember as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("Not found"));

    await useOrgAdminStore.getState().removeMember("org-x", "user-1");
    expect(useOrgAdminStore.getState().toast?.type).toBe("error");
  });

  it("showToast clears previous timer on rapid calls", () => {
    vi.useFakeTimers();

    useOrgAdminStore.getState().showToast("success", "First");
    vi.advanceTimersByTime(1000);
    useOrgAdminStore.getState().showToast("error", "Second");

    // After 2000ms from second toast (total 3000ms from first), toast should still be visible
    vi.advanceTimersByTime(2000);
    expect(useOrgAdminStore.getState().toast).toEqual({ type: "error", message: "Second" });

    // Sprint 213: Error toasts last 6000ms (not 3000ms) — still visible at 5000ms
    vi.advanceTimersByTime(3000);
    expect(useOrgAdminStore.getState().toast).toEqual({ type: "error", message: "Second" });

    // After 6000ms from second toast, it clears
    vi.advanceTimersByTime(1000);
    expect(useOrgAdminStore.getState().toast).toBeNull();

    vi.useRealTimers();
  });
});

// ---------------------------------------------------------------------------
// 6. Sidebar Admin Button Visibility Logic
// ---------------------------------------------------------------------------

describe("Sidebar admin button visibility", () => {
  it("system admin should see Shield button (concept)", () => {
    const context: AdminContext = {
      is_system_admin: true,
      is_org_admin: true,
      admin_org_ids: [],
      enable_org_admin: true,
    };
    const showShield = context.is_system_admin;
    const showBuilding2 = !context.is_system_admin && context.admin_org_ids.length > 0;
    expect(showShield).toBe(true);
    expect(showBuilding2).toBe(false);
  });

  it("org admin should see Building2 button (concept)", () => {
    const context: AdminContext = {
      is_system_admin: false,
      is_org_admin: true,
      admin_org_ids: ["org-x"],
      enable_org_admin: true,
    };
    const showShield = context.is_system_admin;
    const showBuilding2 = !context.is_system_admin && context.admin_org_ids.length > 0;
    expect(showShield).toBe(false);
    expect(showBuilding2).toBe(true);
  });

  it("regular user should see neither button (concept)", () => {
    const context: AdminContext = {
      is_system_admin: false,
      is_org_admin: false,
      admin_org_ids: [],
      enable_org_admin: true,
    };
    const showShield = context.is_system_admin;
    const showBuilding2 = !context.is_system_admin && context.admin_org_ids.length > 0;
    expect(showShield).toBe(false);
    expect(showBuilding2).toBe(false);
  });
});
