import { useAdminStore } from "@/stores/admin-store";
import { useCharacterStore } from "@/stores/character-store";
import { useChatStore } from "@/stores/chat-store";
import { useContextStore } from "@/stores/context-store";
import { useDomainStore } from "@/stores/domain-store";
import { useLivingAgentStore } from "@/stores/living-agent-store";
import { useMemoryStore } from "@/stores/memory-store";
import { useSettingsStore } from "@/stores/settings-store";

export async function revokeServerSession(accessToken: string): Promise<void> {
  if (!accessToken) return;

  const serverUrl = useSettingsStore.getState().settings.server_url;
  if (!serverUrl) return;

  await fetch(`${serverUrl}/api/v1/auth/logout`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function clearLegacyApiKey(): Promise<void> {
  await useSettingsStore.getState().updateSettings({ api_key: "" });
}

export function resetUserScopedStores(): void {
  useChatStore.getState().clearForLogout();
  useMemoryStore.getState().reset();
  useLivingAgentStore.getState().reset();
  useContextStore.getState().stopPolling();
  useContextStore.setState({ info: null, status: "unknown", error: null });
  useCharacterStore.getState().reset();
  useAdminStore.getState().reset();
  useDomainStore.setState({
    domains: [],
    activeDomainId: "maritime",
    orgAllowedDomains: [],
    isLoading: false,
  });
}
