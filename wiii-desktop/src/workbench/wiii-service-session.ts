import { useEffect, useState } from "react";
import { initClient } from "@/api/client";
import { useAuthStore } from "@/stores/auth-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useOrgStore } from "@/stores/org-store";

export function configureWiiiServiceClient(serverUrl: string) {
  const client = initClient(serverUrl, {});
  client.setHeaderResolver(() => useSettingsStore.getState().getAuthHeaders());
  client.setOnUnauthorized(async () => {
    const auth = useAuthStore.getState();
    if (auth.authMode === "oauth") {
      return auth.refreshAccessToken(useSettingsStore.getState().settings.server_url);
    }
    if (auth.authMode === "legacy" && auth.isAuthenticated) await auth.logout();
    return false;
  });
  return client;
}

export function useWiiiServiceSession() {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [configuredFor, setConfiguredFor] = useState<string | null>(null);
  const serverUrl = useSettingsStore((state) => state.settings.server_url);
  const authenticated = useAuthStore((state) => state.isAuthenticated);
  const authMode = useAuthStore((state) => state.authMode);
  const userId = useAuthStore((state) => state.user?.id);
  const sessionKey = JSON.stringify([serverUrl, authMode, userId]);

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setError(null);
    void (async () => {
      try {
        await useSettingsStore.getState().loadSettings();
        if (cancelled) return;
        await useAuthStore.getState().loadAuth();
        if (!cancelled) setLoaded(true);
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      }
    })();
    return () => { cancelled = true; };
  }, [attempt]);

  useEffect(() => {
    if (!loaded || !authenticated || !serverUrl) {
      setConfiguredFor(null);
      return;
    }
    let cancelled = false;
    configureWiiiServiceClient(serverUrl);
    const connection = useConnectionStore.getState();
    connection.startPolling();
    setConfiguredFor(sessionKey);
    void (async () => {
      const org = useOrgStore.getState();
      await org.fetchOrganizations();
      if (cancelled) return;
      await org.fetchAdminContext();
      if (cancelled) return;
      org.setActiveOrg(useSettingsStore.getState().settings.organization_id || null);
    })().catch((reason) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    const timer = authMode === "oauth" ? window.setInterval(() => {
      const auth = useAuthStore.getState();
      if (auth.isTokenExpiringSoon()) void auth.refreshAccessToken(serverUrl);
    }, 60_000) : null;
    return () => {
      cancelled = true;
      connection.stopPolling();
      if (timer !== null) window.clearInterval(timer);
    };
  }, [loaded, authenticated, serverUrl, authMode, sessionKey]);

  return {
    loading: !loaded || (authenticated && !!serverUrl && configuredFor !== sessionKey),
    error,
    retry: () => setAttempt((value) => value + 1),
  };
}
