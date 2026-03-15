import { useAuthStore } from "@/stores/auth-store";
import { useSettingsStore } from "@/stores/settings-store";

export function resolveCurrentChatUserId(): string | null {
  const authState = useAuthStore.getState();
  if (authState.authMode === "oauth" && authState.user?.id) {
    return authState.user.id;
  }

  const userId = useSettingsStore.getState().settings.user_id;
  return userId || null;
}

export function shouldUseServerThreadApis(): boolean {
  const authState = useAuthStore.getState();
  return !(authState.isLoaded && !authState.isAuthenticated);
}
