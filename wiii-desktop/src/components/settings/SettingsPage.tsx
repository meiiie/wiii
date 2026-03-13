/**
 * Settings page — modal overlay for app configuration.
 * Sections: Connection, User, Preferences, Memory, Context.
 * Sprint 105: Context tab + enhanced MemoryTab with search/filter/animation.
 * Sprint 106: Focus trap for accessibility.
 */
import { useState, useMemo, useEffect, useRef } from "react";
import {
  X,
  Server,
  User,
  Palette,
  Brain,
  Database,
  CheckCircle,
  AlertCircle,
  Loader2,
  Trash2,
  Search,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { motion } from "motion/react";
import { useSettingsStore } from "@/stores/settings-store";
import { useUIStore } from "@/stores/ui-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useMemoryStore, FACT_TYPE_LABELS } from "@/stores/memory-store";
import { useContextStore } from "@/stores/context-store";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { staggerContainer, staggerItem } from "@/lib/animations";
import { formatTokens } from "@/lib/format";
import { initClient } from "@/api/client";
import { setTheme } from "@/lib/theme";
import { useOrgStore } from "@/stores/org-store";
import { useDomainStore } from "@/stores/domain-store";
import { useAuthStore } from "@/stores/auth-store";
import { getOrgDisplayName } from "@/lib/org-config";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import { getLlmRuntimeConfig, updateLlmRuntimeConfig } from "@/api/admin";
import { fetchIdentities, unlinkIdentity } from "@/api/users";
import type { AppSettings, LlmRuntimeConfig, UserIdentity } from "@/api/types";
import {
  applyLlmProviderPreset,
  GOOGLE_DEFAULT_MODEL,
  OLLAMA_DEFAULT_BASE_URL,
  OLLAMA_DEFAULT_KEEP_ALIVE,
  OLLAMA_DEFAULT_MODEL,
  OPENROUTER_BASE_URL,
  OPENROUTER_DEFAULT_MODEL,
  OPENROUTER_DEFAULT_MODEL_ADVANCED,
} from "@/lib/llm-presets";
import { OrgSettingsTab } from "./OrgSettingsTab";
import { LivingAgentPanel } from "@/components/living-agent/LivingAgentPanel";
import { Building2, Heart } from "lucide-react";
import {
  clearGeminiApiKey,
  clearOllamaApiKey,
  clearOpenRouterApiKey,
  loadGeminiApiKey,
  loadOpenRouterApiKey,
  loadOllamaApiKey,
  storeFacebookCookie,
  loadFacebookCookie,
  storeGeminiApiKey,
  storeOllamaApiKey,
  storeOpenRouterApiKey,
} from "@/lib/secure-token-storage";

type Tab = "connection" | "profile" | "preferences" | "memory" | "context" | "organization" | "living-agent";

export function SettingsPage() {
  const { settings, updateSettings, resetSettings } = useSettingsStore();
  const { closeSettings } = useUIStore();
  const { checkHealth, status: connStatus } = useConnectionStore();

  const { addToast } = useToastStore();
  const { authMode, user: authUser } = useAuthStore();
  const { activeOrgId, isSystemAdmin, isOrgAdmin } = useOrgStore();
  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [testStatus, setTestStatus] = useState<
    "idle" | "testing" | "success" | "error"
  >("idle");
  const [testMessage, setTestMessage] = useState("");
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Auto-focus close button on mount (Sprint 110)
  useEffect(() => {
    if (dialogRef.current) {
      const firstFocusable = dialogRef.current.querySelector<HTMLElement>(
        'button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      firstFocusable?.focus();
    }
  }, []);

  // Focus trap + Escape to close (Sprint 106)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeSettings();
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeSettings]);

  // Local draft state for connection fields (commit on save)
  // Sprint 194b (H5): facebook_cookie loaded from secure storage, not settings
  const [draft, setDraft] = useState({
    server_url: settings.server_url,
    api_key: settings.api_key,
    facebook_cookie: "",
  });
  // Load facebook cookie from secure storage on mount
  useEffect(() => {
    loadFacebookCookie().then((cookie) => {
      if (cookie) setDraft((d) => ({ ...d, facebook_cookie: cookie }));
    }).catch(() => { /* ignore */ });
  }, []);

  const handleTestConnection = async () => {
    setTestStatus("testing");
    setTestMessage("");

    try {
      // Temporarily init client with draft values to test
      initClient(draft.server_url, {
        "X-API-Key": draft.api_key,
        "X-User-ID": settings.user_id,
        "X-Role": settings.user_role,
      });

      await checkHealth();

      const currentStatus = useConnectionStore.getState().status;
      if (currentStatus === "connected") {
        setTestStatus("success");
        setTestMessage("Wiii nghe thấy bạn rồi!");
      } else {
        setTestStatus("error");
        setTestMessage(
          useConnectionStore.getState().errorMessage || "Không thể kết nối"
        );
      }
    } catch {
      setTestStatus("error");
      setTestMessage("Không thể kết nối đến server");
    }
  };

  const handleSaveConnection = async () => {
    // Sprint 194b (H5): Save facebook_cookie to secure storage, not settings
    if (draft.facebook_cookie) {
      try { await storeFacebookCookie(draft.facebook_cookie); } catch { /* ignore */ }
    }
    await updateSettings({
      server_url: draft.server_url,
      api_key: draft.api_key,
    });

    // Re-init client with new settings
    initClient(draft.server_url, {
      "X-API-Key": draft.api_key,
      "X-User-ID": settings.user_id,
      "X-Role": settings.user_role,
    });

    checkHealth();
    addToast("success", "Wiii ghi nhớ cài đặt rồi!");
  };

  const handleUpdateField = async <K extends keyof AppSettings>(
    key: K,
    value: AppSettings[K]
  ) => {
    await updateSettings({ [key]: value });

    // Apply theme immediately
    if (key === "theme") {
      setTheme(value as "light" | "dark" | "system");
    }

    // Re-init client if auth headers changed
    if (key === "user_id" || key === "user_role") {
      const updated = useSettingsStore.getState().settings;
      initClient(updated.server_url, {
        "X-API-Key": updated.api_key,
        "X-User-ID": updated.user_id,
        "X-Role": updated.user_role,
      });
    }

    addToast("success", "Wiii nhớ rồi!");
  };

  // Sprint 216: Progressive disclosure — dynamic tab visibility
  const isDeveloperMode = authMode === "legacy" || isSystemAdmin();
  const tabs = useMemo(() => {
    const result: { id: Tab; label: string; icon: React.ReactNode }[] = [
      { id: "profile", label: "Hồ sơ", icon: <User size={16} /> },
      { id: "preferences", label: "Tùy chỉnh", icon: <Palette size={16} /> },
      { id: "memory", label: "Trí nhớ", icon: <Brain size={16} /> },
      { id: "context", label: "Ngữ cảnh", icon: <Database size={16} /> },
    ];
    if (isDeveloperMode) {
      result.push({ id: "connection", label: "Kết nối", icon: <Server size={16} /> });
    }
    if (activeOrgId && (isOrgAdmin() || isSystemAdmin())) {
      result.push({ id: "organization", label: "Tổ chức", icon: <Building2 size={16} /> });
    }
    result.push({ id: "living-agent", label: "Linh hồn", icon: <Heart size={16} /> });
    return result;
  }, [isDeveloperMode, activeOrgId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div ref={dialogRef} className="bg-surface rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col border border-border animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <WiiiAvatar state="idle" size={22} />
            <h2 id="settings-title" className="text-lg font-semibold text-text">Cài đặt cho Wiii</h2>
          </div>
          <button
            onClick={closeSettings}
            className="p-1.5 rounded-lg hover:bg-surface-tertiary transition-colors text-text-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border px-5 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-transparent text-text-secondary hover:text-text"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {activeTab === "connection" && (
            <ConnectionTab
              draft={draft}
              setDraft={setDraft}
              testStatus={testStatus}
              testMessage={testMessage}
              connStatus={connStatus}
              onTest={handleTestConnection}
              onSave={handleSaveConnection}
              settings={settings}
              onUpdate={handleUpdateField}
            />
          )}

          {activeTab === "profile" && (
            <UserTab settings={settings} onUpdate={handleUpdateField} />
          )}

          {activeTab === "preferences" && (
            <PreferencesTab settings={settings} onUpdate={handleUpdateField} />
          )}

          {activeTab === "memory" && (
            <MemoryTab userId={authMode === "oauth" && authUser?.id ? authUser.id : settings.user_id} />
          )}

          {activeTab === "context" && (
            <ContextTab />
          )}
          {activeTab === "organization" && (
            <OrgSettingsTab />
          )}
          {activeTab === "living-agent" && (
            <LivingAgentPanel />
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center px-5 py-3 border-t border-border">
          <button
            onClick={() => setShowResetConfirm(true)}
            className="text-sm text-text-tertiary hover:text-red-500 transition-colors"
          >
            Quên tất cả
          </button>
          <button
            onClick={closeSettings}
            className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
          >
            Đóng
          </button>
        </div>

        <ConfirmDialog
          open={showResetConfirm}
          title="Wiii sẽ quên bạn?"
          message="Mọi cài đặt sẽ trở về mặc định. Wiii bắt đầu lại từ đầu. Bạn chắc chắn chứ?"
          confirmLabel="Quên tất cả"
          cancelLabel="Thôi, giữ lại"
          variant="danger"
          onConfirm={async () => {
            await resetSettings();
            // Sprint 194b (H5): Clear facebook cookie from secure storage
            try {
              const { clearFacebookCookie } = await import("@/lib/secure-token-storage");
              await clearFacebookCookie();
              await clearGeminiApiKey();
              await clearOpenRouterApiKey();
              await clearOllamaApiKey();
            } catch { /* ignore */ }
            setDraft({
              server_url: "http://localhost:8000",
              api_key: "local-dev-key",
              facebook_cookie: "",
            });
            setTheme("system");
            setShowResetConfirm(false);
            addToast("success", "Wiii bắt đầu lại. Cảm ơn vì đã quen mình!");
          }}
          onCancel={() => setShowResetConfirm(false)}
        />
      </div>
    </div>
  );
}

/* ===== Connection Tab ===== */
export interface ConnectionTabProps {
  draft: { server_url: string; api_key: string; facebook_cookie: string };
  setDraft: (d: { server_url: string; api_key: string; facebook_cookie: string }) => void;
  testStatus: "idle" | "testing" | "success" | "error";
  testMessage: string;
  connStatus: string;
  onTest: () => void;
  onSave: () => void;
  // Sprint 216: Developer fields moved from Preferences tab
  settings?: AppSettings;
  onUpdate?: <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => void;
}

type GatewayDraft = {
  provider: "google" | "openai" | "openrouter" | "ollama";
  use_multi_agent: boolean;
  google_api_key: string;
  google_model: string;
  openai_api_key: string;
  ollama_api_key: string;
  openai_base_url: string;
  openai_model: string;
  openai_model_advanced: string;
  ollama_base_url: string;
  ollama_model: string;
  ollama_keep_alive: string;
  enable_llm_failover: boolean;
  llm_failover_chain: string;
};
const LEGACY_PAID_OPENAI_MODELS = new Set([
  "gpt-4o-mini",
  "gpt-4o",
  "openai/gpt-4o-mini",
  "openai/gpt-4o",
]);

function applyGatewayProviderDefaults(
  current: GatewayDraft,
  provider: GatewayDraft["provider"]
): GatewayDraft {
  const currentChain = current.llm_failover_chain
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const preset = applyLlmProviderPreset(
    {
      llm_provider: current.provider,
      google_model: current.google_model,
      openai_base_url: current.openai_base_url,
      openai_model: current.openai_model,
      openai_model_advanced: current.openai_model_advanced,
      ollama_base_url: current.ollama_base_url,
      ollama_model: current.ollama_model,
      ollama_keep_alive: current.ollama_keep_alive,
      llm_failover_chain: currentChain,
    },
    provider
  );
  const next: GatewayDraft = {
    ...current,
    provider,
    google_model: preset.google_model ?? current.google_model,
    openai_base_url: preset.openai_base_url ?? current.openai_base_url,
    openai_model: preset.openai_model ?? current.openai_model,
    openai_model_advanced:
      preset.openai_model_advanced ?? current.openai_model_advanced,
    ollama_base_url: preset.ollama_base_url ?? current.ollama_base_url,
    ollama_model: preset.ollama_model ?? current.ollama_model,
    ollama_keep_alive:
      preset.ollama_keep_alive ?? current.ollama_keep_alive,
    llm_failover_chain: (
      Array.isArray(preset.llm_failover_chain)
        ? preset.llm_failover_chain
        : currentChain
    ).join(", "),
  };

  if (provider === "openrouter") {
    if (!next.openai_model || LEGACY_PAID_OPENAI_MODELS.has(next.openai_model)) {
      next.openai_model = OPENROUTER_DEFAULT_MODEL;
    }
    if (
      !next.openai_model_advanced
      || LEGACY_PAID_OPENAI_MODELS.has(next.openai_model_advanced)
    ) {
      next.openai_model_advanced = OPENROUTER_DEFAULT_MODEL_ADVANCED;
    }
  }

  return next;
}

export function ConnectionTab({
  draft,
  setDraft,
  testStatus,
  testMessage,
  onTest,
  onSave,
  settings,
  onUpdate,
}: ConnectionTabProps) {
  const { updateSettings } = useSettingsStore();
  const { addToast } = useToastStore();
  const [gatewayDraft, setGatewayDraft] = useState<GatewayDraft>({
    provider: settings?.llm_provider ?? "ollama",
    use_multi_agent: true,
    google_api_key: "",
    google_model: settings?.google_model ?? GOOGLE_DEFAULT_MODEL,
    openai_api_key: "",
    ollama_api_key: "",
    openai_base_url: settings?.openai_base_url ?? "",
    openai_model: settings?.openai_model ?? OPENROUTER_DEFAULT_MODEL,
    openai_model_advanced:
      settings?.openai_model_advanced ?? OPENROUTER_DEFAULT_MODEL_ADVANCED,
    ollama_base_url: settings?.ollama_base_url ?? OLLAMA_DEFAULT_BASE_URL,
    ollama_model: settings?.ollama_model ?? OLLAMA_DEFAULT_MODEL,
    ollama_keep_alive: settings?.ollama_keep_alive ?? OLLAMA_DEFAULT_KEEP_ALIVE,
    enable_llm_failover: settings?.llm_failover_enabled ?? true,
    llm_failover_chain: (
      settings?.llm_failover_chain ?? ["ollama", "google", "openrouter"]
    ).join(", "),
  });
  const [gatewayInfo, setGatewayInfo] = useState<LlmRuntimeConfig | null>(null);
  const [gatewayState, setGatewayState] = useState<"idle" | "loading" | "saving" | "error">("idle");
  const [gatewayMessage, setGatewayMessage] = useState("");

  useEffect(() => {
    setGatewayDraft((current) => ({
      ...current,
      provider: settings?.llm_provider ?? current.provider,
      use_multi_agent: gatewayInfo?.use_multi_agent ?? current.use_multi_agent,
      google_model: settings?.google_model ?? current.google_model,
      openai_base_url: settings?.openai_base_url ?? current.openai_base_url,
      openai_model: settings?.openai_model ?? current.openai_model,
      openai_model_advanced: settings?.openai_model_advanced ?? current.openai_model_advanced,
      ollama_base_url: settings?.ollama_base_url ?? current.ollama_base_url,
      ollama_model: settings?.ollama_model ?? current.ollama_model,
      ollama_keep_alive: settings?.ollama_keep_alive ?? current.ollama_keep_alive,
      enable_llm_failover: settings?.llm_failover_enabled ?? current.enable_llm_failover,
      llm_failover_chain: (settings?.llm_failover_chain ?? current.llm_failover_chain.split(",").map((item) => item.trim()).filter(Boolean)).join(", "),
    }));
  }, [
    settings?.llm_provider,
    settings?.google_model,
    settings?.openai_base_url,
    settings?.openai_model,
    settings?.openai_model_advanced,
    settings?.ollama_base_url,
    settings?.ollama_model,
    settings?.ollama_keep_alive,
    settings?.llm_failover_enabled,
    settings?.llm_failover_chain,
    gatewayInfo?.use_multi_agent,
  ]);

  useEffect(() => {
    let cancelled = false;

    Promise.all([loadGeminiApiKey(), loadOpenRouterApiKey(), loadOllamaApiKey()])
      .then(([geminiApiKey, openRouterApiKey, ollamaApiKey]) => {
        if (cancelled) return;
        setGatewayDraft((current) => ({
          ...current,
          google_api_key: geminiApiKey ?? current.google_api_key,
          openai_api_key: openRouterApiKey ?? current.openai_api_key,
          ollama_api_key: ollamaApiKey ?? current.ollama_api_key,
        }));
      })
      .catch(() => undefined);

    if (!settings) {
      return () => {
        cancelled = true;
      };
    }

    setGatewayState("loading");
    getLlmRuntimeConfig()
      .then((config) => {
        if (cancelled) return;
        setGatewayInfo(config);
        setGatewayDraft((current) => ({
          ...current,
          provider: config.provider,
          use_multi_agent: config.use_multi_agent,
          google_model: config.google_model,
          openai_base_url: config.openai_base_url ?? current.openai_base_url,
          openai_model: config.openai_model,
          openai_model_advanced: config.openai_model_advanced,
          ollama_base_url: config.ollama_base_url ?? current.ollama_base_url,
          ollama_model: config.ollama_model,
          ollama_keep_alive: config.ollama_keep_alive ?? current.ollama_keep_alive,
          enable_llm_failover: config.enable_llm_failover,
          llm_failover_chain: config.llm_failover_chain.join(", "),
        }));
        setGatewayState("idle");
        setGatewayMessage("");
      })
      .catch(() => {
        if (cancelled) return;
        setGatewayState("error");
        setGatewayMessage("Không đọc được cấu hình LLM runtime từ backend.");
      });

    return () => {
      cancelled = true;
    };
  }, [settings]);

  const refreshGateway = async () => {
    setGatewayState("loading");
    setGatewayMessage("");
    try {
      const config = await getLlmRuntimeConfig();
      setGatewayInfo(config);
      setGatewayDraft((current) => ({
        ...current,
        provider: config.provider,
        use_multi_agent: config.use_multi_agent,
        google_model: config.google_model,
        openai_base_url: config.openai_base_url ?? "",
        openai_model: config.openai_model,
        openai_model_advanced: config.openai_model_advanced,
        ollama_base_url: config.ollama_base_url ?? OLLAMA_DEFAULT_BASE_URL,
        ollama_model: config.ollama_model,
        ollama_keep_alive: config.ollama_keep_alive ?? OLLAMA_DEFAULT_KEEP_ALIVE,
        enable_llm_failover: config.enable_llm_failover,
        llm_failover_chain: config.llm_failover_chain.join(", "),
      }));
      setGatewayState("idle");
    } catch {
      setGatewayState("error");
      setGatewayMessage("Không đọc được cấu hình runtime mới nhất.");
    }
  };

  const handleSaveGateway = async () => {
    const chain = gatewayDraft.llm_failover_chain
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);

    setGatewayState("saving");
    setGatewayMessage("");

    try {
      const runtime = await updateLlmRuntimeConfig({
        provider: gatewayDraft.provider,
        use_multi_agent: gatewayDraft.use_multi_agent,
        google_api_key: gatewayDraft.google_api_key || undefined,
        clear_google_api_key: !gatewayDraft.google_api_key,
        google_model: gatewayDraft.google_model,
        openai_api_key: gatewayDraft.openai_api_key || undefined,
        clear_openai_api_key: !gatewayDraft.openai_api_key,
        ollama_api_key: gatewayDraft.ollama_api_key || undefined,
        clear_ollama_api_key: !gatewayDraft.ollama_api_key,
        openai_base_url: gatewayDraft.openai_base_url,
        openai_model: gatewayDraft.openai_model,
        openai_model_advanced: gatewayDraft.openai_model_advanced,
        ollama_base_url: gatewayDraft.ollama_base_url,
        ollama_model: gatewayDraft.ollama_model,
        ollama_keep_alive: gatewayDraft.ollama_keep_alive,
        enable_llm_failover: gatewayDraft.enable_llm_failover,
        llm_failover_chain: chain,
      });

      if (gatewayDraft.google_api_key) {
        await storeGeminiApiKey(gatewayDraft.google_api_key);
      } else {
        await clearGeminiApiKey();
      }

      if (gatewayDraft.openai_api_key) {
        await storeOpenRouterApiKey(gatewayDraft.openai_api_key);
      } else {
        await clearOpenRouterApiKey();
      }

      if (gatewayDraft.ollama_api_key) {
        await storeOllamaApiKey(gatewayDraft.ollama_api_key);
      } else {
        await clearOllamaApiKey();
      }

      await updateSettings({
        llm_provider: runtime.provider,
        google_model: runtime.google_model,
        openai_base_url: runtime.openai_base_url ?? "",
        openai_model: runtime.openai_model,
        openai_model_advanced: runtime.openai_model_advanced,
        ollama_base_url: runtime.ollama_base_url ?? OLLAMA_DEFAULT_BASE_URL,
        ollama_model: runtime.ollama_model,
        ollama_keep_alive: runtime.ollama_keep_alive ?? OLLAMA_DEFAULT_KEEP_ALIVE,
        llm_failover_enabled: runtime.enable_llm_failover,
        llm_failover_chain: runtime.llm_failover_chain,
      });

      setGatewayInfo(runtime);
      setGatewayDraft((current) => ({
        ...current,
        provider: runtime.provider,
        use_multi_agent: runtime.use_multi_agent,
        google_model: runtime.google_model,
        openai_base_url: runtime.openai_base_url ?? current.openai_base_url,
        openai_model: runtime.openai_model,
        openai_model_advanced: runtime.openai_model_advanced,
        ollama_base_url: runtime.ollama_base_url ?? current.ollama_base_url,
        ollama_model: runtime.ollama_model,
        ollama_keep_alive: runtime.ollama_keep_alive ?? current.ollama_keep_alive,
        enable_llm_failover: runtime.enable_llm_failover,
        llm_failover_chain: runtime.llm_failover_chain.join(", "),
      }));
      setGatewayState("idle");
      setGatewayMessage("Đã áp dụng LLM gateway cho backend hiện tại.");
      addToast("success", "Đã cập nhật cổng model.");
    } catch {
      setGatewayState("error");
      setGatewayMessage("Không thể cập nhật LLM gateway.");
      addToast("error", "Không thể cập nhật cổng model.");
    }
  };

  return (
    <div className="space-y-4">
      <FieldGroup label="Server URL">
        <input
          type="url"
          value={draft.server_url}
          onChange={(e) => setDraft({ ...draft, server_url: e.target.value })}
          placeholder="http://localhost:8000"
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
        />
      </FieldGroup>

      <FieldGroup label="API Key">
        <input
          type="password"
          value={draft.api_key}
          onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
          placeholder="your-api-key"
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
        />
      </FieldGroup>

      {/* Sprint 154: Facebook cookie for logged-in search */}
      <FieldGroup label="Facebook Cookie" hint="Cho phép tìm kiếm trong hội nhóm Facebook. Lấy từ DevTools > Application > Cookies.">
        <input
          type="password"
          value={draft.facebook_cookie}
          onChange={(e) => setDraft({ ...draft, facebook_cookie: e.target.value })}
          placeholder="c_user=...; xs=...; datr=..."
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
        />
      </FieldGroup>

      {/* Test + Save row */}
      <div className="flex gap-3">
        <button
          onClick={onTest}
          disabled={testStatus === "testing"}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-tertiary transition-colors disabled:opacity-50"
        >
          {testStatus === "testing" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : testStatus === "success" ? (
            <CheckCircle size={14} className="text-green-500" />
          ) : testStatus === "error" ? (
            <AlertCircle size={14} className="text-red-500" />
          ) : (
            <Server size={14} />
          )}
          Kiểm tra kết nối
        </button>
        <button
          onClick={onSave}
          className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
        >
          Lưu
        </button>
      </div>

      {/* Test result */}
      {testMessage && (
        <div
          className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
            testStatus === "success"
              ? "bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300"
              : "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300"
          }`}
        >
          {testStatus === "success" ? (
            <CheckCircle size={16} />
          ) : (
            <AlertCircle size={16} />
          )}
          {testMessage}
        </div>
      )}

      {settings && (
        <div className="mt-6 pt-4 border-t border-border space-y-4">
          <div>
            <div className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-1">
              LLM Gateway
            </div>
            <p className="text-xs text-text-tertiary">
              Cấu hình provider runtime cho backend đang chạy. API key được giữ trong secure store của desktop. Local preset mặc định dùng Ollama + Qwen để giảm phụ thuộc cloud.
            </p>
          </div>

          <p className="text-xs text-text-tertiary">
            Current verified local path: backend Docker to native host Ollama
            via host.docker.internal. If you switch to the Docker Ollama
            profile, update the base URL to http://ollama:11434.
          </p>

          <FieldGroup label="Provider">
            <select
              value={gatewayDraft.provider}
              onChange={(e) =>
                setGatewayDraft(
                  applyGatewayProviderDefaults(
                    gatewayDraft,
                    e.target.value as GatewayDraft["provider"]
                  )
                )
              }
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            >
              <option value="google">Google Gemini</option>
              <option value="openrouter">OpenRouter</option>
              <option value="openai">OpenAI Compatible</option>
              <option value="ollama">Ollama</option>
            </select>
          </FieldGroup>

          <FieldGroup label="Gemini API Key">
            <input
              type="password"
              value={gatewayDraft.google_api_key}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, google_api_key: e.target.value })}
              placeholder="AIza..."
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <FieldGroup label="Gemini Model" hint="Gemini la provider native ho tro thinking budget trong runtime hien tai.">
            <input
              type="text"
              value={gatewayDraft.google_model}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, google_model: e.target.value })}
              placeholder={GOOGLE_DEFAULT_MODEL}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <FieldGroup label="OpenRouter / OpenAI API Key">
            <input
              type="password"
              value={gatewayDraft.openai_api_key}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, openai_api_key: e.target.value })}
              placeholder="sk-or-v1-..."
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <FieldGroup label="Ollama API Key" hint="Chỉ cần khi gọi trực tiếp Ollama Cloud. Với Wiii + ChatOllama, dùng host https://ollama.com; client sẽ tự gọi các API path bên dưới. Local Ollama không cần key này.">
            <input
              type="password"
              value={gatewayDraft.ollama_api_key}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, ollama_api_key: e.target.value })}
              placeholder="ollama_api_key"
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <FieldGroup label="OpenAI-Compatible Base URL" hint="Để trống khi dùng OpenAI mặc định. OpenRouter dùng https://openrouter.ai/api/v1.">
            <input
              type="url"
              value={gatewayDraft.openai_base_url}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, openai_base_url: e.target.value })}
              placeholder={OPENROUTER_BASE_URL}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <FieldGroup label="Model">
              <input
                type="text"
                value={gatewayDraft.openai_model}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, openai_model: e.target.value })}
                placeholder={OPENROUTER_DEFAULT_MODEL}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              />
            </FieldGroup>
            <FieldGroup label="Advanced Model">
              <input
                type="text"
                value={gatewayDraft.openai_model_advanced}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, openai_model_advanced: e.target.value })}
                placeholder={OPENROUTER_DEFAULT_MODEL_ADVANCED}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              />
            </FieldGroup>
          </div>

          <div className="text-xs text-text-tertiary">
            Current verified local path: backend Docker to
            http://host.docker.internal:11434. Use http://localhost:11434 only
            when backend runs outside Docker.
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <FieldGroup label="Ollama Base URL" hint="Backend trong Docker dùng http://ollama:11434. Chạy web cục bộ ngoài Docker có thể dùng http://localhost:11434. Với Ollama Cloud trên Wiii, dùng https://ollama.com thay vì thêm /api ở cuối.">
              <input
                type="url"
                value={gatewayDraft.ollama_base_url}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, ollama_base_url: e.target.value })}
                placeholder={OLLAMA_DEFAULT_BASE_URL}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              />
            </FieldGroup>
            <FieldGroup label="Ollama Model" hint="Khuyen dung qwen3:4b-instruct-2507-q4_K_M cho local-first de giam do tre. Co the thay model khac ma khong can sua code backend.">
              <input
                type="text"
                value={gatewayDraft.ollama_model}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, ollama_model: e.target.value })}
                placeholder={OLLAMA_DEFAULT_MODEL}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              />
            </FieldGroup>
            <FieldGroup label="Ollama Keep Alive" hint="Khuyen dung 30m de giam cold-start. Dat 0 de unload ngay, -1 de giu model vo thoi han.">
              <input
                type="text"
                value={gatewayDraft.ollama_keep_alive}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, ollama_keep_alive: e.target.value })}
                placeholder={OLLAMA_DEFAULT_KEEP_ALIVE}
                className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
              />
            </FieldGroup>
          </div>

          <FieldGroup label="Failover Chain" hint="Nhập danh sách provider, cách nhau bởi dấu phẩy. Ví dụ: google, openrouter, ollama">
            <input
              type="text"
              value={gatewayDraft.llm_failover_chain}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, llm_failover_chain: e.target.value })}
              placeholder="google, openrouter, ollama"
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <ToggleField
            label="Bật failover"
            description="Khi provider chính lỗi, backend sẽ thử provider kế tiếp trong chain"
            checked={gatewayDraft.enable_llm_failover}
            onChange={(value) => setGatewayDraft({ ...gatewayDraft, enable_llm_failover: value })}
          />

          <ToggleField
            label="Bat Multi-Agent Graph"
            description="Tat de dung local direct fallback da verify. Bat de quay lai graph/orchestrator path day du."
            checked={gatewayDraft.use_multi_agent}
            onChange={(value) => setGatewayDraft({ ...gatewayDraft, use_multi_agent: value })}
          />

          <div className="flex gap-3">
            <button
              onClick={handleSaveGateway}
              disabled={gatewayState === "saving"}
              className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
            >
              {gatewayState === "saving" ? "Đang áp dụng..." : "Áp dụng gateway"}
            </button>
            <button
              onClick={refreshGateway}
              disabled={gatewayState === "loading"}
              className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-tertiary transition-colors disabled:opacity-50"
            >
              Làm mới
            </button>
          </div>

          {(gatewayMessage || gatewayInfo) && (
            <div className="rounded-lg border border-border bg-surface-secondary p-3 text-sm text-text-secondary space-y-1">
              {gatewayMessage && <div>{gatewayMessage}</div>}
              {gatewayInfo && (
                <>
                  <div>Che do runtime: <span className="font-medium text-text">{gatewayInfo.use_multi_agent ? "multi-agent graph" : "local direct fallback"}</span></div>
                  <div>Provider hiện tại: <span className="font-medium text-text">{gatewayInfo.provider}</span></div>
                  <div>Active provider: <span className="font-medium text-text">{gatewayInfo.active_provider || "chưa khởi tạo"}</span></div>
                  <div>Providers đăng ký: <span className="font-medium text-text">{gatewayInfo.providers_registered.join(", ") || "không có"}</span></div>
                  <div>OpenAI/OpenRouter key runtime: <span className="font-medium text-text">{gatewayInfo.openai_api_key_configured ? "đã cấu hình" : "chưa cấu hình"}</span></div>
                  <div>Ollama key runtime: <span className="font-medium text-text">{gatewayInfo.ollama_api_key_configured ? "đã cấu hình" : "chưa cấu hình"}</span></div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Sprint 216: Developer tools moved from Preferences tab */}
      {settings && onUpdate && (
        <div className="mt-6 pt-4 border-t border-border">
          <div className="text-xs font-medium text-text-tertiary uppercase tracking-wider mb-3">
            Công cụ nhà phát triển
          </div>

          <FieldGroup label="Streaming version">
            <div className="flex gap-2">
              {([
                { value: "v3" as const, label: "V3 (SSE)" },
                { value: "v2" as const, label: "V2" },
                { value: "v1" as const, label: "V1" },
              ]).map((v) => (
                <button
                  key={v.value}
                  onClick={() => onUpdate("streaming_version", v.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    settings.streaming_version === v.value
                      ? "bg-[var(--accent)] text-white"
                      : "border border-border hover:bg-surface-tertiary text-text-secondary"
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </FieldGroup>

          <div className="mt-3">
            <ToggleField
              label="Hiển thị reasoning trace"
              description="Xem chi tiết các bước xử lý"
              checked={settings.show_reasoning_trace}
              onChange={(v) => onUpdate("show_reasoning_trace", v)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== User Tab (Sprint 158: OAuth-aware) ===== */
export interface UserTabProps {
  settings: AppSettings;
  onUpdate: <K extends keyof AppSettings>(
    key: K,
    value: AppSettings[K]
  ) => void;
}

export function UserTab({ settings, onUpdate }: UserTabProps) {
  const { organizations, multiTenantEnabled, activeOrgId, setActiveOrg, orgRole } = useOrgStore();
  // Sprint 218: Subscribe to `domains` so component re-renders after fetchDomains() completes
  const { domains: _domainList, getFilteredDomains, setOrgFilter } = useDomainStore();
  const { updateSettings } = useSettingsStore();
  const { isAuthenticated, user, authMode, logout } = useAuthStore();
  const { addToast } = useToastStore();
  const filteredDomains = getFilteredDomains();
  const isOAuth = authMode === "oauth" && isAuthenticated && user;

  // Linked accounts state (OAuth mode only)
  const [identities, setIdentities] = useState<UserIdentity[]>([]);
  const [identitiesLoading, setIdentitiesLoading] = useState(false);
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null);

  useEffect(() => {
    if (!isOAuth) return;
    let cancelled = false;
    setIdentitiesLoading(true);
    fetchIdentities()
      .then((data) => { if (!cancelled) setIdentities(data); })
      .catch(() => { /* silent — non-critical */ })
      .finally(() => { if (!cancelled) setIdentitiesLoading(false); });
    return () => { cancelled = true; };
  }, [isOAuth]);

  const handleUnlink = async (identityId: string) => {
    setUnlinkingId(identityId);
    try {
      await unlinkIdentity(identityId);
      setIdentities((prev) => prev.filter((i) => i.id !== identityId));
      addToast("success", "Wiii đã hủy liên kết tài khoản");
    } catch {
      addToast("error", "Không thể hủy liên kết");
    } finally {
      setUnlinkingId(null);
    }
  };

  const handleLogout = async () => {
    await logout();
    addToast("success", "Đã đăng xuất");
  };

  // Sprint 215: Compute contextual role label
  const displayRole = (() => {
    if (activeOrgId && orgRole) {
      // In org context → show org membership role
      const orgRoleLabels: Record<string, string> = { owner: "Chủ sở hữu", admin: "Quản trị viên", member: "Thành viên" };
      return orgRoleLabels[orgRole] || "Thành viên";
    }
    // No org → show global role
    const globalRole = isOAuth && user ? user.role : settings.user_role;
    const globalRoleLabels: Record<string, string> = { admin: "Quản trị viên", teacher: "Giảng viên", student: "Người dùng" };
    return globalRoleLabels[globalRole] || "Người dùng";
  })();

  const handleOrgChange = (orgId: string) => {
    const newOrgId = orgId === PERSONAL_ORG_ID ? null : orgId;
    setActiveOrg(newOrgId);
    updateSettings({ organization_id: newOrgId });
    const org = organizations.find((o) => o.id === orgId);
    setOrgFilter(org?.allowed_domains ?? []);
  };

  const PROVIDER_LABELS: Record<string, string> = {
    google: "Google",
    lms: "LMS",
    api_key: "API Key",
  };

  return (
    <div className="space-y-4">
      {/* Sprint 216: OAuth profile card with copy support ID + role badge */}
      {isOAuth && user && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-secondary border border-border">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" className="w-10 h-10 rounded-full" />
          ) : (
            <div className="w-10 h-10 rounded-full bg-[var(--accent-light)] flex items-center justify-center text-[var(--accent)] font-bold text-sm">
              {(user.name || user.email || "?")[0].toUpperCase()}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-text truncate">{user.name || "Chưa đặt tên"}</div>
            <div className="text-xs text-text-tertiary truncate">{user.email}</div>
            <button
              onClick={() => { navigator.clipboard.writeText(user.id); addToast("success", "Đã sao chép mã hỗ trợ"); }}
              className="text-[10px] text-text-tertiary hover:text-text-secondary transition-colors"
              title="Sao chép mã hỗ trợ"
            >
              Sao chép mã hỗ trợ
            </button>
          </div>
          <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[var(--accent-light)] text-[var(--accent)]">
            {displayRole}
          </span>
        </div>
      )}

      {/* Sprint 216: Legacy profile card (consistent with OAuth) */}
      {!isOAuth && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-secondary border border-border">
          <div className="w-10 h-10 rounded-full bg-[var(--accent-light)] flex items-center justify-center text-[var(--accent)] font-bold text-sm">
            {(settings.display_name || "?")[0].toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-text truncate">
              {settings.display_name || "Người dùng"}
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(settings.user_id); addToast("success", "Đã sao chép mã hỗ trợ"); }}
              className="text-[10px] text-text-tertiary hover:text-text-secondary transition-colors"
              title="Sao chép mã hỗ trợ"
            >
              Sao chép mã hỗ trợ
            </button>
          </div>
          <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[var(--accent-light)] text-[var(--accent)]">
            {displayRole}
          </span>
        </div>
      )}

      {/* Name field — editable in both modes */}
      <FieldGroup label="Tên hiển thị" hint="Bảo mình tên bạn để nhớ nhé">
        <input
          type="text"
          value={isOAuth && user ? (user.name || "") : settings.display_name}
          onChange={(e) => onUpdate("display_name", e.target.value)}
          placeholder="Bạn tên gì?"
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
        />
      </FieldGroup>

      {/* OAuth mode: Linked accounts section */}
      {isOAuth && (
        <div>
          <div className="text-sm font-medium text-text-secondary mb-1.5">Tài khoản liên kết</div>
          {identitiesLoading ? (
            <div className="flex items-center gap-2 text-xs text-text-tertiary py-2">
              <Loader2 size={12} className="animate-spin" />
              Đang tải...
            </div>
          ) : identities.length === 0 ? (
            <div className="text-xs text-text-tertiary py-2">Không có tài khoản liên kết</div>
          ) : (
            <div className="space-y-1.5">
              {identities.map((identity) => (
                <div key={identity.id} className="flex items-center gap-2 p-2 rounded-lg border border-border bg-surface-secondary">
                  <span className="text-xs font-bold px-1.5 py-0.5 rounded bg-[var(--accent-light)] text-[var(--accent)]">
                    {PROVIDER_LABELS[identity.provider] || identity.provider}
                  </span>
                  <span className="flex-1 text-xs text-text truncate">{identity.email || identity.display_name || identity.provider_sub}</span>
                  <button
                    onClick={() => handleUnlink(identity.id)}
                    disabled={identities.length <= 1 || unlinkingId === identity.id}
                    className="text-xs text-red-500 hover:text-red-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    title={identities.length <= 1 ? "Không thể hủy tài khoản cuối cùng" : "Hủy liên kết"}
                  >
                    {unlinkingId === identity.id ? <Loader2 size={10} className="animate-spin" /> : "Hủy"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sprint 156: Organization selector (only when multi-tenant) */}
      {multiTenantEnabled && organizations.length > 1 && (
        <FieldGroup label="Không gian làm việc" hint="Chọn tổ chức bạn thuộc về">
          <select
            value={activeOrgId || PERSONAL_ORG_ID}
            onChange={(e) => handleOrgChange(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
          >
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {getOrgDisplayName(org)}
              </option>
            ))}
          </select>
        </FieldGroup>
      )}

      {/* Sprint 215: Domain → "Lĩnh vực kiến thức" + auto-select when single */}
      <FieldGroup label="Lĩnh vực kiến thức" hint="Wiii sẽ ưu tiên tra cứu lĩnh vực này">
        {filteredDomains.length === 1 ? (
          <div className="w-full px-3 py-2 rounded-lg border border-border bg-surface-tertiary text-text text-sm">
            {filteredDomains[0].name_vi || filteredDomains[0].name}
            <span className="block text-xs text-text-tertiary mt-0.5">Tự động — chỉ có 1 lĩnh vực khả dụng</span>
          </div>
        ) : filteredDomains.length > 1 ? (
          <select
            value={settings.default_domain}
            onChange={(e) => onUpdate("default_domain", e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
          >
            {filteredDomains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name_vi || d.name}
              </option>
            ))}
          </select>
        ) : (
          <div className="w-full px-3 py-2 rounded-lg border border-border bg-surface-tertiary text-text-tertiary text-sm">
            Chưa có lĩnh vực
          </div>
        )}
      </FieldGroup>

      {/* Sprint 193: Logout button — visible for all auth modes */}
      <button
        onClick={handleLogout}
        className="w-full px-4 py-2 rounded-lg border border-red-300 dark:border-red-800 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
      >
        Đăng xuất
      </button>
    </div>
  );
}

/* ===== Preferences Tab ===== */
export interface PreferencesTabProps {
  settings: AppSettings;
  onUpdate: <K extends keyof AppSettings>(
    key: K,
    value: AppSettings[K]
  ) => void;
}

export function PreferencesTab({ settings, onUpdate }: PreferencesTabProps) {
  const themes: { value: "light" | "dark" | "system"; label: string }[] = [
    { value: "light", label: "Sáng" },
    { value: "dark", label: "Tối" },
    { value: "system", label: "Hệ thống" },
  ];

  return (
    <div className="space-y-4">
      <FieldGroup label="Giao diện">
        <div className="flex gap-2">
          {themes.map((t) => (
            <button
              key={t.value}
              onClick={() => onUpdate("theme", t.value)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                settings.theme === t.value
                  ? "bg-[var(--accent)] text-white"
                  : "border border-border hover:bg-surface-tertiary text-text-secondary"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </FieldGroup>

      <ToggleField
        label="Hiển thị suy luận"
        description="Xem quá trình suy nghĩ của Wiii"
        checked={settings.show_thinking}
        onChange={(v) => onUpdate("show_thinking", v)}
      />

      {/* Sprint 140: Thinking Level Control */}
      {settings.show_thinking && (
        <FieldGroup label="Mức độ hiển thị suy nghĩ">
          <div className="flex gap-2">
            {([
              { value: "minimal" as const, label: "Tối giản", desc: "Chỉ hiện tiến trình" },
              { value: "balanced" as const, label: "Cân bằng", desc: "Thu gọn suy nghĩ" },
              { value: "detailed" as const, label: "Chi tiết", desc: "Mở rộng tất cả" },
            ]).map((opt) => (
              <button
                key={opt.value}
                onClick={() => onUpdate("thinking_level", opt.value)}
                className={`flex-1 px-3 py-2 rounded-lg text-xs text-center transition-all ${
                  settings.thinking_level === opt.value
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--surface-tertiary)] text-text-secondary hover:bg-[var(--border)]"
                }`}
                title={opt.desc}
              >
                <div className="font-medium">{opt.label}</div>
                <div className={`mt-0.5 text-[10px] ${
                  settings.thinking_level === opt.value ? "text-white/80" : "text-text-tertiary"
                }`}>
                  {opt.desc}
                </div>
              </button>
            ))}
          </div>
        </FieldGroup>
      )}

      {/* Sprint 166: Preview Cards Toggle */}
      <ToggleField
        label="Xem trước nội dung"
        description="Hiển thị thẻ xem trước cho tài liệu, sản phẩm, và liên kết"
        checked={settings.show_previews !== false}
        onChange={(v) => onUpdate("show_previews", v)}
      />

      {/* Sprint 167: Artifacts toggle */}
      <ToggleField
        label="Không gian sáng tạo"
        description="Hiển thị artifact tương tác (code, HTML, bảng dữ liệu) với khả năng thực thi"
        checked={settings.show_artifacts !== false}
        onChange={(v) => onUpdate("show_artifacts", v)}
      />

    </div>
  );
}

/* ===== Memory Tab (Sprint 80, enhanced Sprint 105, Sprint 219: category grouping) ===== */

/** Sprint 219: Category groups for organized memory display */
export const MEMORY_CATEGORIES: { id: string; label: string; types: string[] }[] = [
  { id: "identity", label: "Bản thân", types: ["name", "age", "location", "hometown", "organization", "role", "pronoun_style"] },
  { id: "learning", label: "Học tập", types: ["learning_style", "level", "strength", "weakness", "goal"] },
  { id: "personal", label: "Sở thích", types: ["hobby", "interest", "preference", "emotion", "recent_topic"] },
];

/** Render a memory value in a human-readable way.
 * Some types (e.g. pronoun_style) store a JSON object as their value. */
function formatMemoryValue(type: string, value: string): string {
  if (type === "pronoun_style") {
    try {
      const p = JSON.parse(value) as Record<string, string>;
      const parts: string[] = [];
      if (p.user_called) parts.push(`Wiii gọi bạn: "${p.user_called}"`);
      if (p.ai_self) parts.push(`Wiii tự xưng: "${p.ai_self}"`);
      if (p.user_self) parts.push(`Bạn tự xưng: "${p.user_self}"`);
      return parts.length > 0 ? parts.join(" · ") : value;
    } catch {
      return value;
    }
  }
  return value;
}

export function MemoryTab({ userId }: { userId: string }) {
  const { memories, isLoading, error, fetchMemories, deleteOne, clearAll } =
    useMemoryStore();
  const { addToast } = useToastStore();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  // Fetch on mount and whenever userId changes
  useEffect(() => {
    if (userId) fetchMemories(userId);
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Compute type counts for filter chips
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const mem of memories) {
      counts[mem.type] = (counts[mem.type] || 0) + 1;
    }
    return counts;
  }, [memories]);

  // Filter memories by search + type
  const filteredMemories = useMemo(() => {
    let result = memories;
    if (filterType) {
      result = result.filter((m) => m.type === filterType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (m) =>
          m.value.toLowerCase().includes(q) ||
          (FACT_TYPE_LABELS[m.type] || m.type).toLowerCase().includes(q)
      );
    }
    return result;
  }, [memories, filterType, searchQuery]);

  // Sprint 219: Group filtered memories by category
  const groupedMemories = useMemo(() => {
    const categorizedTypes = new Set(MEMORY_CATEGORIES.flatMap((c) => c.types));
    const groups: { id: string; label: string; items: typeof filteredMemories }[] = [];

    for (const cat of MEMORY_CATEGORIES) {
      const items = filteredMemories.filter((m) => cat.types.includes(m.type));
      if (items.length > 0) {
        groups.push({ id: cat.id, label: cat.label, items });
      }
    }

    // Uncategorized items
    const uncategorized = filteredMemories.filter((m) => !categorizedTypes.has(m.type));
    if (uncategorized.length > 0) {
      groups.push({ id: "other", label: "Khác", items: uncategorized });
    }

    return groups;
  }, [filteredMemories]);

  const handleClearAll = async () => {
    await clearAll(userId);
    setShowClearConfirm(false);
    addToast("success", "Wiii quên hết rồi, bắt đầu lại nha!");
  };

  const handleDeleteOne = async (memoryId: string) => {
    await deleteOne(userId, memoryId);
    addToast("success", "Wiii đã quên điều này");
  };

  const toggleCategory = (categoryId: string) => {
    setCollapsedCategories((prev) => ({
      ...prev,
      [categoryId]: !prev[categoryId],
    }));
  };

  const uniqueTypes = Object.keys(typeCounts).sort();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-text">Wiii nhớ gì về bạn</div>
          <div className="text-xs text-text-tertiary">
            Mình ghi nhớ để hiểu bạn hơn
          </div>
        </div>
        {memories.length > 0 && (
          <button
            onClick={() => setShowClearConfirm(true)}
            disabled={isLoading}
            className="text-xs text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
          >
            Xóa tất cả
          </button>
        )}
      </div>

      <ConfirmDialog
        open={showClearConfirm}
        title="Xóa tất cả bộ nhớ?"
        message="Wiii sẽ quên tất cả thông tin đã ghi nhận về bạn. Bạn không thể hoàn tác."
        confirmLabel="Xóa tất cả"
        cancelLabel="Hủy"
        variant="danger"
        onConfirm={handleClearAll}
        onCancel={() => setShowClearConfirm(false)}
      />

      {/* Search input */}
      {memories.length > 0 && (
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
          />
        </div>
      )}

      {/* Type filter chips */}
      {uniqueTypes.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilterType(null)}
            className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
              filterType === null
                ? "bg-[var(--accent)] text-white"
                : "bg-surface-tertiary text-text-secondary hover:text-text"
            }`}
          >
            Tất cả ({memories.length})
          </button>
          {uniqueTypes.map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(filterType === type ? null : type)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                filterType === type
                  ? "bg-[var(--accent)] text-white"
                  : "bg-surface-tertiary text-text-secondary hover:text-text"
              }`}
            >
              {FACT_TYPE_LABELS[type] || type} ({typeCounts[type]})
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="text-xs text-red-500 p-2 rounded-lg bg-red-50 dark:bg-red-950/30">
          {error}
        </div>
      )}

      {isLoading && memories.length === 0 ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-text-tertiary" />
        </div>
      ) : memories.length === 0 ? (
        <div className="text-center text-text-tertiary text-xs py-8">
          Mình chưa nhớ gì về bạn. Kể cho Wiii nghe nhé!
        </div>
      ) : filteredMemories.length === 0 ? (
        <div className="text-center text-text-tertiary text-xs py-8">
          Không tìm thấy kết quả.
        </div>
      ) : (
        <div className="space-y-3">
          {groupedMemories.map((group) => (
            <div key={group.id} className="rounded-lg border border-border overflow-hidden">
              {/* Category header — collapsible */}
              <button
                onClick={() => toggleCategory(group.id)}
                className="flex items-center justify-between w-full px-3 py-2 bg-surface-secondary hover:bg-surface-tertiary transition-colors"
              >
                <div className="flex items-center gap-2">
                  {collapsedCategories[group.id] ? (
                    <ChevronRight size={14} className="text-text-tertiary" />
                  ) : (
                    <ChevronDown size={14} className="text-text-tertiary" />
                  )}
                  <span className="text-sm font-medium text-text">{group.label}</span>
                </div>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[var(--accent-light)] text-[var(--accent)]">
                  {group.items.length}
                </span>
              </button>

              {/* Category items */}
              {!collapsedCategories[group.id] && (
                <motion.div
                  variants={staggerContainer}
                  initial="hidden"
                  animate="visible"
                  className="divide-y divide-border"
                >
                  {group.items.map((mem) => (
                    <motion.div
                      key={mem.id}
                      variants={staggerItem}
                      className="flex items-center gap-3 px-3 py-2 group"
                    >
                      <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--accent-light)] text-[var(--accent)]">
                        {FACT_TYPE_LABELS[mem.type] || mem.type}
                      </span>
                      <span className="flex-1 text-sm text-text truncate">
                        {formatMemoryValue(mem.type, mem.value)}
                      </span>
                      <span className="shrink-0 text-[10px] text-text-tertiary">
                        {new Date(mem.created_at).toLocaleDateString("vi-VN", {
                          day: "numeric",
                          month: "numeric",
                        })}
                      </span>
                      <button
                        onClick={() => handleDeleteOne(mem.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 transition-all"
                        title="Xóa"
                        aria-label="Xóa thông tin này"
                      >
                        <Trash2 size={12} />
                      </button>
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ===== Context Tab (Sprint 105) ===== */
export function ContextTab() {
  const { info, status, isLoading, error, fetchContextInfo, compact, clear } =
    useContextStore();
  const activeConv = useChatStore((s) => s.activeConversation());
  const sessionId = activeConv?.session_id || activeConv?.id || "";
  const { addToast } = useToastStore();
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // Fetch on mount — Sprint 165: useEffect to avoid setState during render
  useEffect(() => {
    if (sessionId) fetchContextInfo(sessionId);
  }, [sessionId]);

  const utilization = info ? Math.round(info.utilization ?? 0) : 0;
  const totalBudget = info?.total_budget ?? 0;
  const totalUsed = info?.total_used ?? 0;

  const STATUS_BAR_COLORS: Record<string, string> = {
    unknown: "bg-gray-300",
    green: "bg-green-500",
    yellow: "bg-yellow-500",
    orange: "bg-orange-500",
    red: "bg-red-500",
  };

  const handleCompact = async () => {
    await compact(sessionId);
    addToast("success", "Wiii tóm tắt xong rồi!");
  };

  const handleClear = async () => {
    await clear(sessionId);
    setShowClearConfirm(false);
    addToast("success", "Wiii quên cuộc trò chuyện này rồi");
  };

  if (!sessionId) {
    return (
      <div className="text-center text-text-tertiary text-xs py-8">
        Chưa có cuộc trò chuyện nào. Bắt đầu nói chuyện với Wiii nha!
      </div>
    );
  }

  if (isLoading && !info) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={20} className="animate-spin text-text-tertiary" />
      </div>
    );
  }

  if (!info) {
    return (
      <div className="text-center text-text-tertiary text-xs py-8">
        Không thể tải thông tin ngữ cảnh.
        {error && <div className="text-red-500 mt-1">{error}</div>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="text-sm font-medium text-text">Bộ nhớ hội thoại</div>
        <div className="text-xs text-text-tertiary">
          Mình đang theo dõi cuộc trò chuyện này
        </div>
      </div>

      {/* Utilization bar */}
      <div>
        <div className="flex items-center justify-between text-xs text-text-secondary mb-1">
          <span>Sử dụng: {utilization}%</span>
          <span>{formatTokens(totalUsed)}/{formatTokens(totalBudget)} tokens</span>
        </div>
        <div className="w-full h-3 bg-surface-tertiary rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${STATUS_BAR_COLORS[status]}`}
            style={{ width: `${Math.min(utilization, 100)}%` }}
          />
        </div>
      </div>

      {/* Layer breakdown */}
      <div className="space-y-2">
        <div className="text-xs font-medium text-text-secondary">Phân bổ bộ nhớ</div>
        {info.layers && (
          <div className="space-y-1.5">
            <LayerBar label="Cấu hình hệ thống" layer={info.layers.system_prompt} />
            <LayerBar label="Kiến thức về bạn" layer={info.layers.core_memory} />
            <LayerBar label="Tóm tắt" layer={info.layers.summary} />
            <LayerBar label="Tin nhắn" layer={info.layers.recent_messages} />
          </div>
        )}
      </div>

      {/* Message stats */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Bao gồm" value={info.messages_included} />
        <StatCard label="Bị bỏ" value={info.messages_dropped} />
        <StatCard label="Tổng" value={info.total_history_messages} />
      </div>

      {/* Summary info */}
      <div className="text-xs text-text-secondary">
        Tóm tắt: {info.has_summary ? `${info.running_summary_chars} ký tự` : "Chưa có"}
      </div>

      {error && (
        <div className="text-xs text-red-500 p-2 rounded-lg bg-red-50 dark:bg-red-950/30">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={handleCompact}
          disabled={isLoading || !sessionId}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-tertiary transition-colors disabled:opacity-50"
        >
          {isLoading && <Loader2 size={14} className="animate-spin" />}
          Tóm tắt ngay
        </button>
        <button
          onClick={() => setShowClearConfirm(true)}
          disabled={isLoading || !sessionId}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-red-300 dark:border-red-800 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors disabled:opacity-50"
        >
          Xóa ngữ cảnh
        </button>
      </div>

      <ConfirmDialog
        open={showClearConfirm}
        title="Xóa ngữ cảnh hội thoại?"
        message="Tất cả lịch sử hội thoại và tóm tắt sẽ bị xóa. Bạn không thể hoàn tác."
        confirmLabel="Xóa ngữ cảnh"
        cancelLabel="Hủy"
        variant="danger"
        onConfirm={handleClear}
        onCancel={() => setShowClearConfirm(false)}
      />
    </div>
  );
}

/* ===== Context Tab helpers ===== */
export function LayerBar({
  label,
  layer,
}: {
  label: string;
  layer: { budget: number; used: number };
}) {
  const pct = layer.budget > 0 ? Math.round((layer.used / layer.budget) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-text-secondary mb-0.5">
        <span>{label}</span>
        <span>{formatTokens(layer.used)}/{formatTokens(layer.budget)}</span>
      </div>
      <div className="w-full h-1.5 bg-surface-tertiary rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

export function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="p-2 rounded-lg bg-surface-secondary border border-border text-center">
      <div className="text-lg font-semibold text-text">{value}</div>
      <div className="text-[10px] text-text-tertiary">{label}</div>
    </div>
  );
}

/* ===== Shared UI primitives ===== */
export function FieldGroup({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary mb-1.5">
        {label}
      </label>
      {hint && (
        <div className="text-[11px] text-text-tertiary -mt-0.5 mb-1.5">{hint}</div>
      )}
      {children}
    </div>
  );
}

export function ToggleField({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <div className="text-sm font-medium text-text">{label}</div>
        <div className="text-xs text-text-tertiary">{description}</div>
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          checked ? "bg-[var(--accent)]" : "bg-gray-300 dark:bg-gray-600"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}
