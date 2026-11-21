/**
 * Unit tests for settings store and organization preferences.
 * Sprint 215: Added tests for read-only user ID, org-aware role, domain auto-select.
 * Sprint 216: Added tests for tab visibility, progressive disclosure, copy support ID.
 * Sprint 219: Removed Learning tab, Memory category groups.
 * Sprint 219b: Removed pronoun_style from Preferences (auto-detected, not manual).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useSettingsStore } from "@/stores/settings-store";
import { useUIStore } from "@/stores/ui-store";
import { DEFAULT_SERVER_URL } from "@/lib/constants";

// Mock API dependencies for org-store
vi.mock("@/api/organizations", () => ({
  listOrganizations: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgSettings: vi.fn().mockRejectedValue(new Error("Not configured")),
  getOrgPermissions: vi.fn().mockRejectedValue(new Error("Not configured")),
}));
vi.mock("@/api/admin", () => ({
  getAdminContext: vi.fn().mockRejectedValue(new Error("Not configured")),
}));
vi.mock("@/lib/org-branding", () => ({
  applyOrgBranding: vi.fn(),
  resetBranding: vi.fn(),
  DEFAULT_BRANDING: { chatbot_name: "Wiii", welcome_message: "Xin chào!" },
}));
vi.mock("@/lib/constants", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, PERSONAL_ORG_ID: "personal" };
});

// Reset stores before each test
beforeEach(() => {
  useSettingsStore.setState({
    settings: {
      server_url: "http://localhost:8080",
      api_key: "local-dev-key",
      user_id: "test-user-fixed",
      user_role: "student",
      display_name: "User",
      default_domain: "maritime",
      theme: "system",
      language: "vi",
      font_size: "medium",
      show_thinking: true,
      show_reasoning_trace: false,
      streaming_version: "v3",
      thinking_level: "balanced",
    },
    isLoaded: false,
  });
  useUIStore.setState({
    activeView: "chat",
    sidebarOpen: true,
    sourcesPanelOpen: false,
    selectedSourceIndex: null,
  });
});

describe("Settings Store", () => {
  it("should start with default settings", () => {
    const { settings } = useSettingsStore.getState();
    expect(settings.server_url).toBe("http://localhost:8080");
    expect(settings.api_key).toBe("local-dev-key");
    expect(settings.user_id).toBe("test-user-fixed");
    expect(settings.user_role).toBe("student");
    expect(settings.theme).toBe("system");
    expect(settings.show_thinking).toBe(true);
    expect(settings.streaming_version).toBe("v3");
  });

  it("should update partial settings", async () => {
    await useSettingsStore.getState().updateSettings({
      server_url: "http://example.com:9000",
      api_key: "new-key",
    });

    const { settings } = useSettingsStore.getState();
    expect(settings.server_url).toBe("http://example.com:9000");
    expect(settings.api_key).toBe("new-key");
    // Other fields unchanged
    expect(settings.user_id).toBe("test-user-fixed");
    expect(settings.theme).toBe("system");
  });

  it("should update theme setting", async () => {
    await useSettingsStore.getState().updateSettings({ theme: "dark" });
    expect(useSettingsStore.getState().settings.theme).toBe("dark");
  });

  it("should update user role in store (Sprint 215: no longer editable in UI)", async () => {
    await useSettingsStore.getState().updateSettings({ user_role: "teacher" });
    expect(useSettingsStore.getState().settings.user_role).toBe("teacher");
  });

  it("should update streaming version", async () => {
    await useSettingsStore.getState().updateSettings({
      streaming_version: "v2",
    });
    expect(useSettingsStore.getState().settings.streaming_version).toBe("v2");
  });

  it("should reset to defaults", async () => {
    await useSettingsStore.getState().updateSettings({
      server_url: "http://custom:1234",
      theme: "dark",
      user_role: "admin",
    });

    await useSettingsStore.getState().resetSettings();

    const { settings } = useSettingsStore.getState();
    expect(settings.server_url).toBe(DEFAULT_SERVER_URL);
    expect(settings.theme).toBe("system");
    expect(settings.user_role).toBe("student");
  });

  it("should generate auth headers", async () => {
    await useSettingsStore.getState().updateSettings({
      api_key: "test-key-123",
      user_id: "user-456",
      user_role: "teacher",
    });

    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-API-Key"]).toBe("test-key-123");
    expect(headers["X-User-ID"]).toBe("user-456");
    expect(headers["X-Role"]).toBe("teacher");
  });

  it("should include all required header fields", () => {
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers).toHaveProperty("X-API-Key");
    expect(headers).toHaveProperty("X-User-ID");
    expect(headers).toHaveProperty("X-Role");
  });
});

describe("UI Store — Settings View", () => {
  it("should start with activeView = chat", () => {
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("should open settings view", () => {
    useUIStore.getState().openSettings();
    expect(useUIStore.getState().activeView).toBe("settings");
  });

  it("should close settings view", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().closeSettings();
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("should toggle sidebar independently", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().toggleSidebar();

    expect(useUIStore.getState().activeView).toBe("settings");
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });
});

describe("Settings — Display Name & Domain", () => {
  it("should update display name", async () => {
    await useSettingsStore.getState().updateSettings({
      display_name: "Captain Nguyễn",
    });
    expect(useSettingsStore.getState().settings.display_name).toBe(
      "Captain Nguyễn"
    );
  });

  it("should update default domain", async () => {
    await useSettingsStore.getState().updateSettings({
      default_domain: "traffic_law",
    });
    expect(useSettingsStore.getState().settings.default_domain).toBe(
      "traffic_law"
    );
  });

  it("should update language", async () => {
    await useSettingsStore.getState().updateSettings({ language: "en" });
    expect(useSettingsStore.getState().settings.language).toBe("en");
  });

  it("should update font size", async () => {
    await useSettingsStore.getState().updateSettings({ font_size: "large" });
    expect(useSettingsStore.getState().settings.font_size).toBe("large");
  });

  it("should toggle show_reasoning_trace", async () => {
    expect(useSettingsStore.getState().settings.show_reasoning_trace).toBe(
      false
    );
    await useSettingsStore.getState().updateSettings({
      show_reasoning_trace: true,
    });
    expect(useSettingsStore.getState().settings.show_reasoning_trace).toBe(
      true
    );
  });
});

// ---------------------------------------------------------------------------
// Sprint 215: "Hồ Sơ Thật" — Settings User Tab UX Overhaul
// ---------------------------------------------------------------------------
import { useOrgStore } from "@/stores/org-store";

describe("Sprint 215 — User ID read-only", () => {
  it("should preserve user_id in settings store (sent via X-User-ID)", () => {
    const { settings } = useSettingsStore.getState();
    expect(settings.user_id).toBe("test-user-fixed");
    // user_id is still stored and used in headers — just not editable in UI
    const headers = useSettingsStore.getState().getAuthHeaders();
    expect(headers["X-User-ID"]).toBe("test-user-fixed");
  });

  it("should still allow programmatic user_id update (store-level)", async () => {
    await useSettingsStore.getState().updateSettings({ user_id: "new-id" });
    expect(useSettingsStore.getState().settings.user_id).toBe("new-id");
  });
});

describe("Sprint 215 — Org-aware role display", () => {
  beforeEach(() => {
    useOrgStore.setState({
      activeOrgId: null,
      orgRole: null,
      organizations: [],
      multiTenantEnabled: false,
      permissions: [],
      orgSettings: null,
    });
  });

  it("should store orgRole from permissions response", () => {
    useOrgStore.setState({ orgRole: "admin", activeOrgId: "org-1" });
    expect(useOrgStore.getState().orgRole).toBe("admin");
  });

  it("should reset orgRole when switching to personal workspace", () => {
    useOrgStore.setState({ orgRole: "owner", activeOrgId: "org-1" });
    // Simulate switch to personal
    useOrgStore.setState({ orgRole: null, activeOrgId: null });
    expect(useOrgStore.getState().orgRole).toBeNull();
  });

  it("should default orgRole to null", () => {
    expect(useOrgStore.getState().orgRole).toBeNull();
  });

  it("should support all 3 org role values", () => {
    for (const role of ["member", "admin", "owner"]) {
      useOrgStore.setState({ orgRole: role });
      expect(useOrgStore.getState().orgRole).toBe(role);
    }
  });
});

describe("Sprint 215 — Domain label and auto-select", () => {
  it("should still store default_domain in settings", async () => {
    await useSettingsStore.getState().updateSettings({ default_domain: "traffic_law" });
    expect(useSettingsStore.getState().settings.default_domain).toBe("traffic_law");
  });

  it("should preserve domain setting across updates", async () => {
    await useSettingsStore.getState().updateSettings({ default_domain: "maritime" });
    await useSettingsStore.getState().updateSettings({ display_name: "Test" });
    expect(useSettingsStore.getState().settings.default_domain).toBe("maritime");
  });
});

describe("Sprint 216 — Developer fields moved to Connection tab", () => {
  it("should still store streaming_version (moved, not removed)", async () => {
    await useSettingsStore.getState().updateSettings({ streaming_version: "v2" });
    expect(useSettingsStore.getState().settings.streaming_version).toBe("v2");
  });

  it("should still store show_reasoning_trace (moved, not removed)", async () => {
    await useSettingsStore.getState().updateSettings({ show_reasoning_trace: true });
    expect(useSettingsStore.getState().settings.show_reasoning_trace).toBe(true);
  });
});
