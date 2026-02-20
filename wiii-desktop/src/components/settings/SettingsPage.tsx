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
  GraduationCap,
  CheckCircle,
  AlertCircle,
  Loader2,
  Trash2,
  Search,
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
import { fetchPreferences, updatePreferences } from "@/api/preferences";
import { useOrgStore } from "@/stores/org-store";
import { useDomainStore } from "@/stores/domain-store";
import { useAuthStore } from "@/stores/auth-store";
import { getOrgDisplayName } from "@/lib/org-config";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import { fetchIdentities, unlinkIdentity } from "@/api/users";
import type { AppSettings, UserRole, UserPreferences, UserIdentity, LearningStyle, DifficultyLevel, PronounStyle } from "@/api/types";
import { OrgSettingsTab } from "./OrgSettingsTab";
import { Building2 } from "lucide-react";

type Tab = "connection" | "user" | "preferences" | "learning" | "memory" | "context" | "organization";

export function SettingsPage() {
  const { settings, updateSettings, resetSettings } = useSettingsStore();
  const { closeSettings } = useUIStore();
  const { checkHealth, status: connStatus } = useConnectionStore();

  const { addToast } = useToastStore();
  const [activeTab, setActiveTab] = useState<Tab>("connection");
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
  const [draft, setDraft] = useState({
    server_url: settings.server_url,
    api_key: settings.api_key,
    facebook_cookie: settings.facebook_cookie || "",
  });

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
    await updateSettings({
      server_url: draft.server_url,
      api_key: draft.api_key,
      facebook_cookie: draft.facebook_cookie,
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

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "connection", label: "Kết nối", icon: <Server size={16} /> },
    { id: "user", label: "Người dùng", icon: <User size={16} /> },
    { id: "preferences", label: "Giao diện", icon: <Palette size={16} /> },
    { id: "learning", label: "Học tập", icon: <GraduationCap size={16} /> },
    { id: "memory", label: "Bộ nhớ", icon: <Brain size={16} /> },
    { id: "context", label: "Ngữ cảnh", icon: <Database size={16} /> },
    { id: "organization", label: "Tổ chức", icon: <Building2 size={16} /> },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div ref={dialogRef} className="bg-surface rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col border border-border animate-scale-in">
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
            />
          )}

          {activeTab === "user" && (
            <UserTab settings={settings} onUpdate={handleUpdateField} />
          )}

          {activeTab === "preferences" && (
            <PreferencesTab settings={settings} onUpdate={handleUpdateField} />
          )}

          {activeTab === "learning" && (
            <LearningTab />
          )}

          {activeTab === "memory" && (
            <MemoryTab userId={settings.user_id} />
          )}

          {activeTab === "context" && (
            <ContextTab />
          )}
          {activeTab === "organization" && (
            <OrgSettingsTab />
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
interface ConnectionTabProps {
  draft: { server_url: string; api_key: string; facebook_cookie: string };
  setDraft: (d: { server_url: string; api_key: string; facebook_cookie: string }) => void;
  testStatus: "idle" | "testing" | "success" | "error";
  testMessage: string;
  connStatus: string;
  onTest: () => void;
  onSave: () => void;
}

function ConnectionTab({
  draft,
  setDraft,
  testStatus,
  testMessage,
  onTest,
  onSave,
}: ConnectionTabProps) {
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
    </div>
  );
}

/* ===== User Tab (Sprint 158: OAuth-aware) ===== */
interface UserTabProps {
  settings: AppSettings;
  onUpdate: <K extends keyof AppSettings>(
    key: K,
    value: AppSettings[K]
  ) => void;
}

function UserTab({ settings, onUpdate }: UserTabProps) {
  const { organizations, multiTenantEnabled, activeOrgId, setActiveOrg } = useOrgStore();
  const { getFilteredDomains, setOrgFilter } = useDomainStore();
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

  const roles: { value: UserRole; label: string }[] = [
    { value: "student", label: "Sinh viên" },
    { value: "teacher", label: "Giảng viên" },
    { value: "admin", label: "Quản trị viên" },
  ];

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
      {/* OAuth mode: show profile from server */}
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
          </div>
          <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[var(--accent-light)] text-[var(--accent)]">
            {user.role === "admin" ? "Quản trị" : user.role === "teacher" ? "Giảng viên" : "Sinh viên"}
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

      {/* Legacy mode only: User ID + Role */}
      {!isOAuth && (
        <>
          <FieldGroup label="User ID">
            <input
              type="text"
              value={settings.user_id}
              onChange={(e) => onUpdate("user_id", e.target.value)}
              placeholder="desktop-user"
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
            />
          </FieldGroup>

          <FieldGroup label="Vai trò">
            <div className="flex gap-2">
              {roles.map((r) => (
                <button
                  key={r.value}
                  onClick={() => onUpdate("user_role", r.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    settings.user_role === r.value
                      ? "bg-[var(--accent)] text-white"
                      : "border border-border hover:bg-surface-tertiary text-text-secondary"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </FieldGroup>
        </>
      )}

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

      {/* Domain default — now shows only org-filtered domains */}
      <FieldGroup label="Domain mặc định">
        {filteredDomains.length > 0 ? (
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
          <input
            type="text"
            value={settings.default_domain}
            onChange={(e) => onUpdate("default_domain", e.target.value)}
            placeholder="maritime"
            className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent"
          />
        )}
      </FieldGroup>

      {/* OAuth mode: Logout button */}
      {isOAuth && (
        <button
          onClick={handleLogout}
          className="w-full px-4 py-2 rounded-lg border border-red-300 dark:border-red-800 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
        >
          Đăng xuất
        </button>
      )}
    </div>
  );
}

/* ===== Preferences Tab ===== */
interface PreferencesTabProps {
  settings: AppSettings;
  onUpdate: <K extends keyof AppSettings>(
    key: K,
    value: AppSettings[K]
  ) => void;
}

function PreferencesTab({ settings, onUpdate }: PreferencesTabProps) {
  const themes: { value: "light" | "dark" | "system"; label: string }[] = [
    { value: "light", label: "Sáng" },
    { value: "dark", label: "Tối" },
    { value: "system", label: "Hệ thống" },
  ];

  const streamingVersions: {
    value: "v1" | "v2" | "v3";
    label: string;
  }[] = [
    { value: "v3", label: "V3 (SSE)" },
    { value: "v2", label: "V2" },
    { value: "v1", label: "V1" },
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

      <FieldGroup label="Streaming version">
        <div className="flex gap-2">
          {streamingVersions.map((v) => (
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

      <ToggleField
        label="Hiển thị reasoning trace"
        description="Xem chi tiết các bước xử lý"
        checked={settings.show_reasoning_trace}
        onChange={(v) => onUpdate("show_reasoning_trace", v)}
      />
    </div>
  );
}

/* ===== Learning Tab (Sprint 120) ===== */
const LEARNING_STYLES: { value: LearningStyle; label: string; desc: string }[] = [
  { value: "mixed", label: "Tổng hợp", desc: "Kết hợp nhiều phương pháp" },
  { value: "visual", label: "Hình ảnh", desc: "Sơ đồ, biểu đồ, hình minh họa" },
  { value: "reading", label: "Đọc hiểu", desc: "Tài liệu, bài viết chi tiết" },
  { value: "quiz", label: "Trắc nghiệm", desc: "Hỏi đáp, kiểm tra kiến thức" },
  { value: "interactive", label: "Tương tác", desc: "Thực hành, mô phỏng" },
];

const DIFFICULTY_LEVELS: { value: DifficultyLevel; label: string; desc: string }[] = [
  { value: "beginner", label: "Cơ bản", desc: "Mới bắt đầu tìm hiểu" },
  { value: "intermediate", label: "Trung bình", desc: "Có kiến thức nền tảng" },
  { value: "advanced", label: "Nâng cao", desc: "Hiểu sâu chuyên ngành" },
  { value: "expert", label: "Chuyên gia", desc: "Kinh nghiệm thực tế dày dặn" },
];

const PRONOUN_STYLES: { value: PronounStyle; label: string; desc: string }[] = [
  { value: "auto", label: "Tự động", desc: "Wiii sẽ tự điều chỉnh theo bạn" },
  { value: "casual", label: "Thân mật", desc: "Mình/cậu, tớ/bạn" },
  { value: "formal", label: "Trang trọng", desc: "Tôi/bạn, em/anh/chị" },
];

function LearningTab() {
  const { addToast } = useToastStore();
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Fetch on mount
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchPreferences()
      .then((data) => {
        if (!cancelled) setPrefs(data);
      })
      .catch(() => {
        if (!cancelled) setError("Không thể tải cài đặt học tập");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleUpdate = async (field: string, value: string) => {
    if (!prefs) return;
    setSaving(true);
    try {
      const updated = await updatePreferences({ [field]: value });
      setPrefs(updated);
      addToast("success", "Wiii nhớ rồi!");
    } catch {
      addToast("error", "Không thể lưu. Thử lại nhé!");
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={20} className="animate-spin text-text-tertiary" />
      </div>
    );
  }

  if (error || !prefs) {
    return (
      <div className="text-center py-8">
        <div className="text-xs text-text-tertiary mb-2">
          {error || "Không thể tải cài đặt"}
        </div>
        <button
          onClick={() => window.location.reload()}
          className="text-xs text-[var(--accent)] hover:underline"
        >
          Thử lại
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="text-sm font-medium text-text">Phong cách học tập</div>
        <div className="text-xs text-text-tertiary">
          Wiii sẽ điều chỉnh cách trả lời phù hợp với bạn
        </div>
      </div>

      <FieldGroup label="Phương pháp học" hint="Bạn thích học theo cách nào?">
        <div className="space-y-1.5">
          {LEARNING_STYLES.map((s) => (
            <button
              key={s.value}
              onClick={() => handleUpdate("learning_style", s.value)}
              disabled={saving}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                prefs.learning_style === s.value
                  ? "bg-[var(--accent-light)] border border-[var(--accent)] text-text"
                  : "border border-border hover:bg-surface-tertiary text-text-secondary"
              }`}
            >
              <span className="font-medium">{s.label}</span>
              <span className="text-xs text-text-tertiary ml-2">{s.desc}</span>
            </button>
          ))}
        </div>
      </FieldGroup>

      <FieldGroup label="Mức độ" hint="Trình độ hiện tại của bạn">
        <div className="grid grid-cols-2 gap-1.5">
          {DIFFICULTY_LEVELS.map((d) => (
            <button
              key={d.value}
              onClick={() => handleUpdate("difficulty", d.value)}
              disabled={saving}
              className={`text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                prefs.difficulty === d.value
                  ? "bg-[var(--accent-light)] border border-[var(--accent)] text-text"
                  : "border border-border hover:bg-surface-tertiary text-text-secondary"
              }`}
            >
              <div className="font-medium">{d.label}</div>
              <div className="text-[10px] text-text-tertiary">{d.desc}</div>
            </button>
          ))}
        </div>
      </FieldGroup>

      <FieldGroup label="Cách xưng hô" hint="Wiii nói chuyện với bạn thế nào?">
        <div className="flex gap-2">
          {PRONOUN_STYLES.map((p) => (
            <button
              key={p.value}
              onClick={() => handleUpdate("pronoun_style", p.value)}
              disabled={saving}
              className={`flex-1 text-center px-3 py-2 rounded-lg text-sm transition-colors ${
                prefs.pronoun_style === p.value
                  ? "bg-[var(--accent)] text-white"
                  : "border border-border hover:bg-surface-tertiary text-text-secondary"
              }`}
              title={p.desc}
            >
              {p.label}
            </button>
          ))}
        </div>
      </FieldGroup>

      {saving && (
        <div className="flex items-center gap-2 text-xs text-text-tertiary">
          <Loader2 size={12} className="animate-spin" />
          Đang lưu...
        </div>
      )}
    </div>
  );
}

/* ===== Memory Tab (Sprint 80, enhanced Sprint 105) ===== */
function MemoryTab({ userId }: { userId: string }) {
  const { memories, isLoading, error, fetchMemories, deleteOne, clearAll } =
    useMemoryStore();
  const { addToast } = useToastStore();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string | null>(null);

  // Fetch on mount
  const [loaded, setLoaded] = useState(false);
  if (!loaded) {
    setLoaded(true);
    fetchMemories(userId);
  }

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

  const handleClearAll = async () => {
    await clearAll(userId);
    setShowClearConfirm(false);
    addToast("success", "Wiii quên hết rồi, bắt đầu lại nha!");
  };

  const handleDeleteOne = async (memoryId: string) => {
    await deleteOne(userId, memoryId);
    addToast("success", "Wiii đã quên điều này");
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
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          className="space-y-1.5"
        >
          {filteredMemories.map((mem) => (
            <motion.div
              key={mem.id}
              variants={staggerItem}
              className="flex items-center gap-3 px-3 py-2 rounded-lg border border-border bg-surface-secondary group"
            >
              <span className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--accent-light)] text-[var(--accent)]">
                {FACT_TYPE_LABELS[mem.type] || mem.type}
              </span>
              <span className="flex-1 text-sm text-text truncate">
                {mem.value}
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
  );
}

/* ===== Context Tab (Sprint 105) ===== */
function ContextTab() {
  const { info, status, isLoading, error, fetchContextInfo, compact, clear } =
    useContextStore();
  const activeConv = useChatStore((s) => s.activeConversation());
  const sessionId = activeConv?.session_id || activeConv?.id || "";
  const { addToast } = useToastStore();
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  // Fetch on mount
  const [loaded, setLoaded] = useState(false);
  if (!loaded) {
    setLoaded(true);
    if (sessionId) fetchContextInfo(sessionId);
  }

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
        <div className="text-xs font-medium text-text-secondary">Token layers</div>
        {info.layers && (
          <div className="space-y-1.5">
            <LayerBar label="System Prompt" layer={info.layers.system_prompt} />
            <LayerBar label="Core Memory" layer={info.layers.core_memory} />
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
          Xóa context
        </button>
      </div>

      <ConfirmDialog
        open={showClearConfirm}
        title="Xóa context hội thoại?"
        message="Tất cả lịch sử hội thoại và tóm tắt sẽ bị xóa. Bạn không thể hoàn tác."
        confirmLabel="Xóa context"
        cancelLabel="Hủy"
        variant="danger"
        onConfirm={handleClear}
        onCancel={() => setShowClearConfirm(false)}
      />
    </div>
  );
}

/* ===== Context Tab helpers ===== */
function LayerBar({
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

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="p-2 rounded-lg bg-surface-secondary border border-border text-center">
      <div className="text-lg font-semibold text-text">{value}</div>
      <div className="text-[10px] text-text-tertiary">{label}</div>
    </div>
  );
}

/* ===== Shared UI primitives ===== */
function FieldGroup({
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

function ToggleField({
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
