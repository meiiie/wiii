/**
 * OrgManagerSettings — Sprint 181: Branding-only settings for org admins.
 *
 * Org admins can change: display name, welcome message, colors.
 * Features, AI config, and permissions are NOT exposed.
 */
import { useEffect, useState, useMemo } from "react";
import { Save } from "lucide-react";
import { useOrgAdminStore } from "@/stores/org-admin-store";

export function OrgManagerSettings({ orgId }: { orgId: string }) {
  const { orgSettings, fetchSettings, updateSettings } = useOrgAdminStore();
  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [chatbotName, setChatbotName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#AE5630");
  const [saving, setSaving] = useState(false);

  // Load current settings
  useEffect(() => {
    fetchSettings(orgId);
  }, [orgId, fetchSettings]);

  // Sync form state with loaded settings
  useEffect(() => {
    if (orgSettings?.branding) {
      setWelcomeMessage(orgSettings.branding.welcome_message || "");
      setChatbotName(orgSettings.branding.chatbot_name || "Wiii");
      setPrimaryColor(orgSettings.branding.primary_color || "#AE5630");
    }
  }, [orgSettings]);

  // Dirty state tracking — detect unsaved changes
  const isDirty = useMemo(() => {
    if (!orgSettings?.branding) return false;
    const orig = orgSettings.branding;
    return (
      chatbotName !== (orig.chatbot_name || "Wiii") ||
      welcomeMessage !== (orig.welcome_message || "") ||
      primaryColor !== (orig.primary_color || "#AE5630")
    );
  }, [orgSettings, chatbotName, welcomeMessage, primaryColor]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(orgId, {
        branding: {
          welcome_message: welcomeMessage,
          chatbot_name: chatbotName,
          primary_color: primaryColor,
        },
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h3 className="text-sm font-semibold text-text mb-4">Tuỳ chỉnh giao diện</h3>
        <p className="text-xs text-text-tertiary mb-4">
          Thay đổi cách Wiii hiển thị cho tổ chức của bạn.
        </p>
      </div>

      {/* Chatbot name */}
      <div className="space-y-1.5">
        <label htmlFor="org-chatbot-name" className="text-sm font-medium text-text">Tên chatbot</label>
        <input
          id="org-chatbot-name"
          type="text"
          value={chatbotName}
          onChange={(e) => setChatbotName(e.target.value)}
          maxLength={50}
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          placeholder="Wiii"
        />
      </div>

      {/* Welcome message */}
      <div className="space-y-1.5">
        <label htmlFor="org-welcome-message" className="text-sm font-medium text-text">Lời chào</label>
        <textarea
          id="org-welcome-message"
          value={welcomeMessage}
          onChange={(e) => setWelcomeMessage(e.target.value)}
          rows={3}
          maxLength={500}
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-none"
          placeholder="Xin chào! Mình là Wiii"
        />
      </div>

      {/* Primary color */}
      <div className="space-y-1.5">
        <label htmlFor="org-primary-color" className="text-sm font-medium text-text">Màu chủ đạo</label>
        <div className="flex items-center gap-3">
          <input
            id="org-primary-color"
            type="color"
            value={primaryColor}
            onChange={(e) => setPrimaryColor(e.target.value)}
            className="w-10 h-10 rounded-lg border border-border cursor-pointer"
            aria-label="Màu chủ đạo"
          />
          <code className="text-xs text-text-secondary bg-surface-tertiary px-2 py-1 rounded">
            {primaryColor}
          </code>
        </div>
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving || !isDirty}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
      >
        <Save size={14} />
        {saving ? "Đang lưu..." : "Lưu cài đặt"}
      </button>

      {/* Info about restricted settings */}
      <div className="bg-surface-tertiary rounded-lg p-3 text-xs text-text-tertiary">
        Các cài đặt nâng cao (tính năng AI, quyền truy cập, lĩnh vực) cần liên hệ quản trị hệ thống.
      </div>
    </div>
  );
}
