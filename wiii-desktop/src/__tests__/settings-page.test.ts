/**
 * Unit tests for SettingsPage component logic & settings store.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useSettingsStore } from "@/stores/settings-store";
import { useUIStore } from "@/stores/ui-store";

// Reset stores before each test
beforeEach(() => {
  useSettingsStore.setState({
    settings: {
      server_url: "http://localhost:8000",
      api_key: "local-dev-key",
      user_id: "desktop-user",
      user_role: "student",
      display_name: "User",
      default_domain: "maritime",
      theme: "system",
      language: "vi",
      font_size: "medium",
      show_thinking: true,
      show_reasoning_trace: false,
      streaming_version: "v3",
    },
    isLoaded: false,
  });
  useUIStore.setState({
    sidebarOpen: true,
    settingsOpen: false,
    sourcesPanelOpen: false,
    selectedSourceIndex: null,
  });
});

describe("Settings Store", () => {
  it("should start with default settings", () => {
    const { settings } = useSettingsStore.getState();
    expect(settings.server_url).toBe("http://localhost:8000");
    expect(settings.api_key).toBe("local-dev-key");
    expect(settings.user_id).toBe("desktop-user");
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
    expect(settings.user_id).toBe("desktop-user");
    expect(settings.theme).toBe("system");
  });

  it("should update theme setting", async () => {
    await useSettingsStore.getState().updateSettings({ theme: "dark" });
    expect(useSettingsStore.getState().settings.theme).toBe("dark");
  });

  it("should update user role", async () => {
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
    expect(settings.server_url).toBe("http://localhost:8000");
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

describe("UI Store — Settings Modal", () => {
  it("should start with settingsOpen = false", () => {
    expect(useUIStore.getState().settingsOpen).toBe(false);
  });

  it("should open settings modal", () => {
    useUIStore.getState().openSettings();
    expect(useUIStore.getState().settingsOpen).toBe(true);
  });

  it("should close settings modal", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().closeSettings();
    expect(useUIStore.getState().settingsOpen).toBe(false);
  });

  it("should toggle sidebar independently", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().toggleSidebar();

    expect(useUIStore.getState().settingsOpen).toBe(true);
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
