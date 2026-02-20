/**
 * OrgSettingsTab — org admin panel for branding, features, AI config.
 * Sprint 161: "Không Gian Riêng" — Phase 3 admin panel.
 *
 * Only visible to users with "manage:settings" permission.
 * Renders inside the existing SettingsPage modal.
 */
import { useState, useEffect } from "react";
import { useOrgStore } from "@/stores/org-store";
import { updateOrgSettings } from "@/api/organizations";
import { PermissionGate } from "@/components/common/PermissionGate";
import { Palette, Sliders, Brain, Sparkles } from "lucide-react";

export function OrgSettingsTab() {
  const { activeOrgId, orgSettings, fetchOrgSettings } = useOrgStore();
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  // Local form state
  const [chatbotName, setChatbotName] = useState("");
  const [welcomeMessage, setWelcomeMessage] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#AE5630");
  const [accentColor, setAccentColor] = useState("#C4633A");
  const [personaOverlay, setPersonaOverlay] = useState("");
  const [enableProductSearch, setEnableProductSearch] = useState(false);
  const [enableDeepScanning, setEnableDeepScanning] = useState(false);
  const [enableThinkingChain, setEnableThinkingChain] = useState(false);
  const [quickStartQuestions, setQuickStartQuestions] = useState("");

  // Sync form state from orgSettings
  useEffect(() => {
    if (orgSettings) {
      setChatbotName(orgSettings.branding.chatbot_name);
      setWelcomeMessage(orgSettings.branding.welcome_message);
      setPrimaryColor(orgSettings.branding.primary_color);
      setAccentColor(orgSettings.branding.accent_color);
      setPersonaOverlay(orgSettings.ai_config.persona_prompt_overlay ?? "");
      setEnableProductSearch(orgSettings.features.enable_product_search);
      setEnableDeepScanning(orgSettings.features.enable_deep_scanning);
      setEnableThinkingChain(orgSettings.features.enable_thinking_chain);
      setQuickStartQuestions(
        (orgSettings.onboarding.quick_start_questions ?? []).join("\n"),
      );
    }
  }, [orgSettings]);

  const handleSave = async () => {
    if (!activeOrgId) return;
    setSaving(true);
    setSaveMsg(null);

    try {
      const patch = {
        branding: {
          chatbot_name: chatbotName,
          welcome_message: welcomeMessage,
          primary_color: primaryColor,
          accent_color: accentColor,
        },
        ai_config: {
          persona_prompt_overlay: personaOverlay || null,
        },
        features: {
          enable_product_search: enableProductSearch,
          enable_deep_scanning: enableDeepScanning,
          enable_thinking_chain: enableThinkingChain,
        },
        onboarding: {
          quick_start_questions: quickStartQuestions
            .split("\n")
            .map((q) => q.trim())
            .filter(Boolean),
        },
      };

      await updateOrgSettings(activeOrgId, patch);
      await fetchOrgSettings(activeOrgId);
      setSaveMsg("Đã lưu thành công!");
    } catch (err) {
      setSaveMsg("Lỗi: " + (err instanceof Error ? err.message : "Không thể lưu"));
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  };

  if (!activeOrgId) {
    return (
      <div className="text-sm text-text-tertiary text-center py-8">
        Chọn một tổ chức để quản lý cài đặt.
      </div>
    );
  }

  return (
    <PermissionGate
      action="manage"
      resource="settings"
      fallback={
        <div className="text-sm text-text-tertiary text-center py-8">
          Bạn cần quyền quản trị viên để thay đổi cài đặt tổ chức.
        </div>
      }
    >
      <div className="space-y-6">
        {/* Branding Section */}
        <section>
          <h3 className="flex items-center gap-2 text-sm font-medium text-text mb-3">
            <Palette size={16} />
            Thương hiệu
          </h3>
          <div className="space-y-3">
            <label className="block">
              <span className="text-xs text-text-secondary">Tên chatbot</span>
              <input
                type="text"
                value={chatbotName}
                onChange={(e) => setChatbotName(e.target.value)}
                className="mt-1 w-full h-9 px-3 rounded-lg bg-surface-secondary border border-border text-sm text-text focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                placeholder="Wiii"
              />
            </label>
            <label className="block">
              <span className="text-xs text-text-secondary">Lời chào welcome</span>
              <input
                type="text"
                value={welcomeMessage}
                onChange={(e) => setWelcomeMessage(e.target.value)}
                className="mt-1 w-full h-9 px-3 rounded-lg bg-surface-secondary border border-border text-sm text-text focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                placeholder="Xin chào! Mình là Wiii"
              />
            </label>
            <div className="flex gap-3">
              <label className="flex-1">
                <span className="text-xs text-text-secondary">Màu chính</span>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-9 h-9 rounded-lg border border-border cursor-pointer"
                  />
                  <input
                    type="text"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="flex-1 h-9 px-3 rounded-lg bg-surface-secondary border border-border text-sm text-text font-mono focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                  />
                </div>
              </label>
              <label className="flex-1">
                <span className="text-xs text-text-secondary">Màu nhấn</span>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="color"
                    value={accentColor}
                    onChange={(e) => setAccentColor(e.target.value)}
                    className="w-9 h-9 rounded-lg border border-border cursor-pointer"
                  />
                  <input
                    type="text"
                    value={accentColor}
                    onChange={(e) => setAccentColor(e.target.value)}
                    className="flex-1 h-9 px-3 rounded-lg bg-surface-secondary border border-border text-sm text-text font-mono focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                  />
                </div>
              </label>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section>
          <h3 className="flex items-center gap-2 text-sm font-medium text-text mb-3">
            <Sliders size={16} />
            Tính năng
          </h3>
          <div className="space-y-2">
            {[
              { label: "Tìm kiếm sản phẩm", value: enableProductSearch, setter: setEnableProductSearch },
              { label: "Quét sâu (Deep Scanning)", value: enableDeepScanning, setter: setEnableDeepScanning },
              { label: "Chuỗi tư duy (Thinking Chain)", value: enableThinkingChain, setter: setEnableThinkingChain },
            ].map(({ label, value, setter }) => (
              <label key={label} className="flex items-center justify-between py-1.5 cursor-pointer">
                <span className="text-sm text-text-secondary">{label}</span>
                <button
                  onClick={() => setter(!value)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    value ? "bg-[var(--accent)]" : "bg-surface-tertiary"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
                      value ? "left-[22px]" : "left-0.5"
                    }`}
                  />
                </button>
              </label>
            ))}
          </div>
        </section>

        {/* AI Config Section */}
        <section>
          <h3 className="flex items-center gap-2 text-sm font-medium text-text mb-3">
            <Brain size={16} />
            AI Persona
          </h3>
          <label className="block">
            <span className="text-xs text-text-secondary">
              Hướng dẫn bổ sung cho AI (persona overlay)
            </span>
            <textarea
              value={personaOverlay}
              onChange={(e) => setPersonaOverlay(e.target.value)}
              rows={3}
              className="mt-1 w-full px-3 py-2 rounded-lg bg-surface-secondary border border-border text-sm text-text resize-y focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              placeholder='VD: "Bạn là trợ lý AI của UBND Phường Lưu Kiếm. Trả lời với giọng trang trọng."'
            />
          </label>
        </section>

        {/* Onboarding Section */}
        <section>
          <h3 className="flex items-center gap-2 text-sm font-medium text-text mb-3">
            <Sparkles size={16} />
            Onboarding
          </h3>
          <label className="block">
            <span className="text-xs text-text-secondary">
              Câu hỏi gợi ý (mỗi dòng 1 câu)
            </span>
            <textarea
              value={quickStartQuestions}
              onChange={(e) => setQuickStartQuestions(e.target.value)}
              rows={3}
              className="mt-1 w-full px-3 py-2 rounded-lg bg-surface-secondary border border-border text-sm text-text resize-y focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              placeholder={"Giải thích Quy tắc 15 COLREGs\nMức phạt vượt đèn đỏ?\nCách tính thuế GTGT"}
            />
          </label>
        </section>

        {/* Save Button */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-9 px-5 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
          >
            {saving ? "Đang lưu..." : "Lưu cài đặt"}
          </button>
          {saveMsg && (
            <span className={`text-xs ${saveMsg.startsWith("Lỗi") ? "text-red-500" : "text-green-600"}`}>
              {saveMsg}
            </span>
          )}
        </div>
      </div>
    </PermissionGate>
  );
}
