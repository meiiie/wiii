/**
 * Root App component — initializes stores, mounts layout.
 * Sprint 106: Loading screen during init.
 */
import { useEffect } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { ChatView } from "@/components/chat/ChatView";
import { SettingsPage } from "@/components/settings";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { useSettingsStore } from "@/stores/settings-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useContextStore } from "@/stores/context-store";
import { useDomainStore } from "@/stores/domain-store";
import { useChatStore } from "@/stores/chat-store";
import { useUIStore } from "@/stores/ui-store";
import { useToastStore } from "@/stores/toast-store";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { CommandPalette } from "@/components/common/CommandPalette";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { initClient } from "@/api/client";
import { AvatarPreview } from "@/components/common/AvatarPreview";

export default function App() {
  // Dev tool: ?preview=avatar shows avatar preview page
  if (window.location.search.includes("preview=avatar")) {
    return <AvatarPreview />;
  }

  const { loadSettings, settings, isLoaded: settingsLoaded } = useSettingsStore();
  const { startPolling, stopPolling, setOnReconnect } = useConnectionStore();
  const { startPolling: startContextPolling, stopPolling: stopContextPolling } =
    useContextStore();
  const { fetchDomains } = useDomainStore();
  const { loadConversations, isLoaded: chatsLoaded } = useChatStore();
  const { settingsOpen, commandPaletteOpen, closeCommandPalette } = useUIStore();
  const { addToast } = useToastStore();

  // Register global keyboard shortcuts
  useKeyboardShortcuts();

  // Initialize on mount
  useEffect(() => {
    async function init() {
      // 1. Load persisted settings
      await loadSettings();
      // 2. Load persisted conversations
      await loadConversations();
    }
    init();
  }, [loadSettings, loadConversations]);

  // When settings are loaded, initialize client and start health polling
  useEffect(() => {
    if (settings.server_url) {
      // Initialize HTTP client with current settings
      initClient(settings.server_url, {
        "X-API-Key": settings.api_key,
        "X-User-ID": settings.user_id,
        "X-Role": settings.user_role,
      });

      // Start health check polling
      startPolling();

      // Register reconnection celebration
      setOnReconnect(() => addToast("success", "Wiii đã quay lại rồi nè! ✨"));

      // Fetch available domains
      fetchDomains();
    }

    return () => {
      stopPolling();
    };
  }, [settings.server_url, settings.api_key, settings.user_id, settings.user_role, startPolling, stopPolling, fetchDomains, setOnReconnect, addToast]);

  // Start context polling when active conversation changes (handles mid-session creation)
  const activeConv = useChatStore((s) => s.activeConversation());
  const sessionId = activeConv?.session_id || activeConv?.id || "";
  useEffect(() => {
    if (sessionId && settings.server_url) {
      startContextPolling(sessionId);
    }
    return () => {
      stopContextPolling();
    };
  }, [sessionId, settings.server_url, startContextPolling, stopContextPolling]);

  // Loading screen while stores initialize
  if (!settingsLoaded || !chatsLoaded) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-surface">
        <div className="flex flex-col items-center gap-4">
          <WiiiAvatar state="thinking" size={48} />
          <span className="text-sm text-text-tertiary">Wiii đang thức dậy...</span>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <AppShell>
        <ChatView />
      </AppShell>
      {settingsOpen && <SettingsPage />}
      <CommandPalette open={commandPaletteOpen} onClose={closeCommandPalette} />
    </ErrorBoundary>
  );
}
