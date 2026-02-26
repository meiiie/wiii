/**
 * Keyboard shortcuts hook.
 * Sprint 81: Enhanced keyboard navigation.
 *
 * - Ctrl+N / Ctrl+Shift+N: New conversation
 * - Ctrl+,: Open settings
 * - Ctrl+B: Toggle sidebar
 * - Ctrl+K: Command palette
 * - Ctrl+/: Toggle thinking display
 * - Ctrl+I: Toggle context panel
 * - Escape: Close any open modal/panel
 */
import { useEffect } from "react";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useContextStore } from "@/stores/context-store";

export function useKeyboardShortcuts() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isCtrl = e.ctrlKey || e.metaKey;
      const ui = useUIStore.getState();

      // Escape — close any open modal/panel or navigate back to chat
      if (e.key === "Escape") {
        if (ui.commandPaletteOpen) {
          e.preventDefault();
          ui.closeCommandPalette();
          return;
        }
        // Sprint 192: Escape from any admin/settings view → back to chat
        if (ui.activeView !== "chat") {
          e.preventDefault();
          ui.navigateToChat();
          return;
        }
        const ctx = useContextStore.getState();
        if (ctx.isPanelOpen) {
          e.preventDefault();
          ctx.togglePanel();
          return;
        }
      }

      // Ctrl+K — command palette
      if (isCtrl && e.key === "k") {
        e.preventDefault();
        ui.toggleCommandPalette();
        return;
      }

      // Ctrl+N or Ctrl+Shift+N — new conversation
      if (isCtrl && e.key === "n") {
        e.preventDefault();
        useChatStore.getState().createConversation();
        return;
      }

      // Ctrl+, — open settings
      if (isCtrl && e.key === ",") {
        e.preventDefault();
        ui.openSettings();
        return;
      }

      // Ctrl+B — toggle sidebar
      if (isCtrl && e.key === "b") {
        e.preventDefault();
        ui.toggleSidebar();
        return;
      }

      // Ctrl+I — toggle context panel
      if (isCtrl && e.key === "i") {
        e.preventDefault();
        useContextStore.getState().togglePanel();
        return;
      }

      // Ctrl+/ — toggle thinking display
      if (isCtrl && e.key === "/") {
        e.preventDefault();
        const current = useSettingsStore.getState().settings.show_thinking;
        useSettingsStore.getState().updateSettings({ show_thinking: !current });
        return;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
}
