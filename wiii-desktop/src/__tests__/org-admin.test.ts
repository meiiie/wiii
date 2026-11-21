/**
 * Sprint 181: "Hai Tầng Quyền Lực" — Desktop Tests
 *
 * Tests for:
 *   - AdminContext type and API function
 *   - org-store: adminContext state, fetchAdminContext, isSystemAdmin, isOrgAdmin
 *   - ui-store: activeView, open/close actions
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock API dependencies for org-store
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgPermissions: vi.fn().mockRejectedValue(new Error("Not configured")),
  updateOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgHostActionEvents: vi.fn().mockResolvedValue({ entries: [], total: 0, limit: 20, offset: 0 }),
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
