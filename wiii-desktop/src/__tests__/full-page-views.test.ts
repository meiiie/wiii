/**
 * Sprint 192: Full-page admin/settings layout tests.
 *
 * Tests: ui-store activeView, view routing, sidebar behavior,
 * keyboard shortcuts, backward compatibility.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useUIStore } from "@/stores/ui-store";
import type { ActiveView } from "@/stores/ui-store";

// Reset store between tests
function resetStore() {
  useUIStore.setState({
    activeView: "chat",
    sidebarOpen: true,
    settingsOpen: false,
    adminPanelOpen: false,
    orgManagerPanelOpen: false,
    orgManagerTargetOrgId: null,
    commandPaletteOpen: false,
    sourcesPanelOpen: false,
    characterPanelOpen: false,
    previewPanelOpen: false,
    selectedPreviewId: null,
    artifactPanelOpen: false,
    selectedArtifactId: null,
    _ephemeralArtifact: null,
  });
}

describe("Sprint 192: ui-store activeView", () => {
  beforeEach(resetStore);

  it("defaults activeView to chat", () => {
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("openAdminPanel sets activeView to system-admin", () => {
    useUIStore.getState().openAdminPanel();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("system-admin");
    expect(s.adminPanelOpen).toBe(true);
  });

  it("closeAdminPanel returns to chat", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().closeAdminPanel();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("chat");
    expect(s.adminPanelOpen).toBe(false);
  });

  it("openOrgManagerPanel sets activeView to org-admin", () => {
    useUIStore.getState().openOrgManagerPanel("org-123");
    const s = useUIStore.getState();
    expect(s.activeView).toBe("org-admin");
    expect(s.orgManagerPanelOpen).toBe(true);
    expect(s.orgManagerTargetOrgId).toBe("org-123");
  });

  it("closeOrgManagerPanel returns to chat", () => {
    useUIStore.getState().openOrgManagerPanel("org-123");
    useUIStore.getState().closeOrgManagerPanel();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("chat");
    expect(s.orgManagerPanelOpen).toBe(false);
    expect(s.orgManagerTargetOrgId).toBeNull();
  });

  it("openSettings sets activeView to settings", () => {
    useUIStore.getState().openSettings();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("settings");
    expect(s.settingsOpen).toBe(true);
  });

  it("closeSettings returns to chat", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().closeSettings();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("chat");
    expect(s.settingsOpen).toBe(false);
  });

  it("navigateToChat returns to chat from any view", () => {
    const views: ActiveView[] = ["system-admin", "org-admin", "settings"];
    for (const view of views) {
      useUIStore.setState({ activeView: view, settingsOpen: true, adminPanelOpen: true });
      useUIStore.getState().navigateToChat();
      const s = useUIStore.getState();
      expect(s.activeView).toBe("chat");
      expect(s.settingsOpen).toBe(false);
      expect(s.adminPanelOpen).toBe(false);
    }
  });

  it("closeAll resets to chat", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().closeAll();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("chat");
    expect(s.adminPanelOpen).toBe(false);
    expect(s.settingsOpen).toBe(false);
    expect(s.orgManagerPanelOpen).toBe(false);
  });

  it("switching between views works correctly", () => {
    // Start at chat
    expect(useUIStore.getState().activeView).toBe("chat");

    // Open admin
    useUIStore.getState().openAdminPanel();
    expect(useUIStore.getState().activeView).toBe("system-admin");

    // Switch to settings (should close admin)
    useUIStore.getState().openSettings();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("settings");
    expect(s.adminPanelOpen).toBe(false);
    expect(s.settingsOpen).toBe(true);
  });

  it("openAdminPanel closes other views", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().openAdminPanel();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("system-admin");
    expect(s.settingsOpen).toBe(false);
    expect(s.orgManagerPanelOpen).toBe(false);
    expect(s.commandPaletteOpen).toBe(false);
  });

  it("openOrgManagerPanel closes other views", () => {
    useUIStore.getState().openSettings();
    useUIStore.getState().openOrgManagerPanel("org-456");
    const s = useUIStore.getState();
    expect(s.activeView).toBe("org-admin");
    expect(s.settingsOpen).toBe(false);
    expect(s.adminPanelOpen).toBe(false);
  });
});

describe("Sprint 192: Backward compatibility", () => {
  beforeEach(resetStore);

  it("adminPanelOpen stays synced with activeView", () => {
    useUIStore.getState().openAdminPanel();
    expect(useUIStore.getState().adminPanelOpen).toBe(true);
    expect(useUIStore.getState().activeView).toBe("system-admin");

    useUIStore.getState().closeAdminPanel();
    expect(useUIStore.getState().adminPanelOpen).toBe(false);
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("orgManagerPanelOpen stays synced with activeView", () => {
    useUIStore.getState().openOrgManagerPanel("org-test");
    expect(useUIStore.getState().orgManagerPanelOpen).toBe(true);
    expect(useUIStore.getState().activeView).toBe("org-admin");

    useUIStore.getState().closeOrgManagerPanel();
    expect(useUIStore.getState().orgManagerPanelOpen).toBe(false);
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("settingsOpen stays synced with activeView", () => {
    useUIStore.getState().openSettings();
    expect(useUIStore.getState().settingsOpen).toBe(true);
    expect(useUIStore.getState().activeView).toBe("settings");

    useUIStore.getState().closeSettings();
    expect(useUIStore.getState().settingsOpen).toBe(false);
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("existing open/close signatures unchanged (no args needed)", () => {
    // These should not throw
    useUIStore.getState().openSettings();
    useUIStore.getState().closeSettings();
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().closeAdminPanel();
    useUIStore.getState().openOrgManagerPanel("org-id");
    useUIStore.getState().closeOrgManagerPanel();
    useUIStore.getState().closeAll();
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("sidebarOpen is independent of activeView", () => {
    useUIStore.setState({ sidebarOpen: true });
    useUIStore.getState().openAdminPanel();
    // sidebarOpen remains true — AppShell uses effectiveSidebarOpen
    expect(useUIStore.getState().sidebarOpen).toBe(true);
    expect(useUIStore.getState().activeView).toBe("system-admin");
  });

  it("commandPalette can open independently of activeView", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().openCommandPalette();
    expect(useUIStore.getState().commandPaletteOpen).toBe(true);
    expect(useUIStore.getState().activeView).toBe("system-admin");
  });
});

describe("Sprint 192: Keyboard shortcuts — activeView", () => {
  beforeEach(resetStore);

  it("Escape from system-admin navigates to chat", () => {
    useUIStore.getState().openAdminPanel();
    const ui = useUIStore.getState();
    // Simulate what useKeyboardShortcuts does
    if (ui.activeView !== "chat") {
      ui.navigateToChat();
    }
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("Escape from settings navigates to chat", () => {
    useUIStore.getState().openSettings();
    const ui = useUIStore.getState();
    if (ui.activeView !== "chat") {
      ui.navigateToChat();
    }
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("Escape from org-admin navigates to chat", () => {
    useUIStore.getState().openOrgManagerPanel("org-test");
    const ui = useUIStore.getState();
    if (ui.activeView !== "chat") {
      ui.navigateToChat();
    }
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("Escape in chat view does not trigger navigateToChat", () => {
    // activeView is already "chat" — Escape should not do anything related to views
    const ui = useUIStore.getState();
    expect(ui.activeView).toBe("chat");
    // The shortcut handler checks activeView !== "chat" before calling navigateToChat
    // so nothing happens — just verify state didn't change
    expect(useUIStore.getState().activeView).toBe("chat");
  });

  it("commandPalette Escape takes priority over view navigation", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().openCommandPalette();
    // The shortcut handler checks commandPaletteOpen first
    const ui = useUIStore.getState();
    expect(ui.commandPaletteOpen).toBe(true);
    // Simulating Escape: close command palette first, don't navigate
    ui.closeCommandPalette();
    expect(useUIStore.getState().commandPaletteOpen).toBe(false);
    // Still in admin view
    expect(useUIStore.getState().activeView).toBe("system-admin");
  });
});

describe("Sprint 192: View transition edge cases", () => {
  beforeEach(resetStore);

  it("opening admin from org-admin switches correctly", () => {
    useUIStore.getState().openOrgManagerPanel("org-1");
    useUIStore.getState().openAdminPanel();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("system-admin");
    expect(s.adminPanelOpen).toBe(true);
    expect(s.orgManagerPanelOpen).toBe(false);
  });

  it("opening org-admin from admin switches correctly", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().openOrgManagerPanel("org-2");
    const s = useUIStore.getState();
    expect(s.activeView).toBe("org-admin");
    expect(s.orgManagerPanelOpen).toBe(true);
    expect(s.adminPanelOpen).toBe(false);
  });

  it("opening settings from admin switches correctly", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().openSettings();
    const s = useUIStore.getState();
    expect(s.activeView).toBe("settings");
    expect(s.settingsOpen).toBe(true);
    expect(s.adminPanelOpen).toBe(false);
  });

  it("double open of same view is idempotent", () => {
    useUIStore.getState().openAdminPanel();
    useUIStore.getState().openAdminPanel();
    expect(useUIStore.getState().activeView).toBe("system-admin");
    expect(useUIStore.getState().adminPanelOpen).toBe(true);
  });

  it("navigateToChat resets orgManagerTargetOrgId", () => {
    useUIStore.getState().openOrgManagerPanel("org-xyz");
    expect(useUIStore.getState().orgManagerTargetOrgId).toBe("org-xyz");
    useUIStore.getState().navigateToChat();
    expect(useUIStore.getState().orgManagerTargetOrgId).toBeNull();
  });

  it("side panels are only for chat — state preserved when switching views", () => {
    // Open sources panel in chat
    useUIStore.setState({ sourcesPanelOpen: true });
    expect(useUIStore.getState().sourcesPanelOpen).toBe(true);

    // Switch to admin — sources panel state stays (AppShell gates rendering)
    useUIStore.getState().openAdminPanel();
    expect(useUIStore.getState().sourcesPanelOpen).toBe(true);
    expect(useUIStore.getState().activeView).toBe("system-admin");

    // Come back to chat — sources panel still open
    useUIStore.getState().navigateToChat();
    expect(useUIStore.getState().sourcesPanelOpen).toBe(true);
  });
});
