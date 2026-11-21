import { LoginScreen } from "@/components/auth/LoginScreen";
import { WiiiConnectPage } from "@/components/connect/WiiiConnectPage";
import { TitleBar } from "@/components/layout/TitleBar";
import { useAuthStore } from "@/stores/auth-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useOrgStore } from "@/stores/org-store";
import { PERSONAL_ORG_ID } from "@/lib/constants";
import { BootFailure, BootSplash } from "./WorkbenchBoot";
import { useWiiiServiceSession } from "./wiii-service-session";

export function WiiiServiceSurface({ view, onBack, onOpenConnect }: {
  view: "service" | "connect";
  onBack: () => void;
  onOpenConnect: () => void;
}) {
  const { loading, error, retry } = useWiiiServiceSession();
  const authenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const settings = useSettingsStore((state) => state.settings);
  const updateSettings = useSettingsStore((state) => state.updateSettings);
  const status = useConnectionStore((state) => state.status);
  const organizations = useOrgStore((state) => state.organizations);
  const activeOrgId = useOrgStore((state) => state.activeOrgId);
  const setActiveOrg = useOrgStore((state) => state.setActiveOrg);

  if (error) return <BootFailure error={error} onRetry={retry} />;
  if (loading) return <BootSplash label="Wiii đang kết nối Service..." />;
  if (!authenticated || !settings.server_url) return <LoginScreen onOpenLocal={onBack} />;
  if (view === "connect") return (
    <div className="flex h-screen min-h-0 flex-col bg-surface">
      <TitleBar minimal />
      <div className="min-h-0 flex-1"><WiiiConnectPage onClose={onBack} backLabel="Quay lại Neko" /></div>
    </div>
  );

  const statusLabel = {
    connected: "Đã kết nối", degraded: "Kết nối không ổn định",
    disconnected: "Chưa kết nối", checking: "Đang kiểm tra",
  }[status];
  const buttonClass = "rounded-xl border border-[var(--nk-border)] px-4 py-2 text-sm hover:bg-[var(--nk-raised)] focus-visible:outline focus-visible:outline-2";

  return (
    <div className="nk-root flex h-screen flex-col bg-[var(--nk-canvas)] text-[var(--nk-text)]">
      <TitleBar minimal />
      <main className="min-h-0 flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <button className={buttonClass} onClick={onBack}>Quay lại Neko</button>
        <header>
          <h1 className="text-2xl font-semibold">Wiii Service</h1>
          <p className="mt-2 text-sm text-[var(--nk-text-2)]">Tài khoản, tổ chức và kết nối của bạn.</p>
        </header>
        <section className="space-y-5 rounded-2xl border border-[var(--nk-border)] bg-[var(--nk-composer)] p-6" aria-label="Tài khoản Wiii Service">
          <div>
            <h2 className="font-medium">{user?.name || settings.display_name || "Tài khoản API"}</h2>
            {user?.email && <p className="text-sm text-[var(--nk-text-2)]">{user.email}</p>}
          </div>
          <dl className="space-y-2 text-sm">
            <div><dt className="text-[var(--nk-text-2)]">Máy chủ Service</dt><dd className="break-all">{settings.server_url}</dd></div>
            <div><dt className="text-[var(--nk-text-2)]">Trạng thái kết nối</dt><dd role="status">{statusLabel}</dd></div>
          </dl>
          {organizations.length > 1 && (
            <label className="block text-sm">Tổ chức
              <select className="mt-2 block w-full rounded-lg border border-[var(--nk-border)] bg-[var(--nk-canvas)] p-2"
                value={activeOrgId || PERSONAL_ORG_ID}
                onChange={(event) => {
                  const id = event.target.value === PERSONAL_ORG_ID ? null : event.target.value;
                  setActiveOrg(id);
                  void updateSettings({ organization_id: id });
                }}>
                {organizations.map((org) => <option key={org.id} value={org.id}>{org.display_name || org.name}</option>)}
              </select>
            </label>
          )}
          <div className="flex flex-wrap gap-3">
            <button className={buttonClass} onClick={onOpenConnect}>Tài khoản &amp; ứng dụng</button>
            <button className={buttonClass} onClick={() => void logout()}>Đăng xuất</button>
          </div>
        </section>
      </div>
      </main>
    </div>
  );
}
