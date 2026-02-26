/**
 * Audit Logs tab — dual subtab for admin actions + auth events.
 * Sprint 179: "Quản Trị Toàn Diện"
 */
import { useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";
import type { AuditSubTab } from "@/stores/admin-store";

const PAGE_SIZE = 20;

const SUB_TABS: { id: AuditSubTab; label: string }[] = [
  { id: "admin", label: "Hành động admin" },
  { id: "auth", label: "Sự kiện xác thực" },
];

export function AuditLogsTab() {
  const {
    auditSubTab,
    setAuditSubTab,
    auditLogs,
    auditLogsTotal,
    auditLogsPage,
    authEvents,
    authEventsTotal,
    authEventsPage,
    loading,
    fetchAuditLogs,
    fetchAuthEvents,
  } = useAdminStore();

  useEffect(() => {
    if (auditSubTab === "admin") {
      fetchAuditLogs(0);
    } else {
      fetchAuthEvents(0);
    }
  }, [auditSubTab, fetchAuditLogs, fetchAuthEvents]);

  const handleSubTabChange = (tab: AuditSubTab) => {
    setAuditSubTab(tab);
  };

  return (
    <div className="space-y-4">
      {/* Subtabs */}
      <div className="flex gap-1.5">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleSubTabChange(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              auditSubTab === tab.id
                ? "bg-[var(--accent)] text-white"
                : "bg-surface-secondary text-text-secondary hover:text-text border border-border"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {auditSubTab === "admin" ? (
        <AdminAuditTable
          entries={auditLogs}
          total={auditLogsTotal}
          page={auditLogsPage}
          loading={loading}
          onPageChange={(p) => fetchAuditLogs(p)}
        />
      ) : (
        <AuthEventsTable
          entries={authEvents}
          total={authEventsTotal}
          page={authEventsPage}
          loading={loading}
          onPageChange={(p) => fetchAuthEvents(p)}
        />
      )}
    </div>
  );
}

function AdminAuditTable({
  entries,
  total,
  page,
  loading,
  onPageChange,
}: {
  entries: { id: string; actor_name: string; action: string; target_type: string; target_id: string; ip_address: string; occurred_at: string | null }[];
  total: number;
  page: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-secondary text-text-secondary text-left">
              <th className="px-4 py-2.5 font-medium">Thời gian</th>
              <th className="px-4 py-2.5 font-medium">Người thực hiện</th>
              <th className="px-4 py-2.5 font-medium">Hành động</th>
              <th className="px-4 py-2.5 font-medium">Đối tượng</th>
              <th className="px-4 py-2.5 font-medium">IP</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && !loading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-text-tertiary text-xs">
                  Không có nhật ký
                </td>
              </tr>
            )}
            {entries.map((entry) => (
              <tr
                key={entry.id}
                className="border-t border-border hover:bg-surface-secondary transition-colors"
              >
                <td className="px-4 py-2.5 text-xs text-text-tertiary whitespace-nowrap">
                  {entry.occurred_at
                    ? new Date(entry.occurred_at).toLocaleString("vi-VN")
                    : "—"}
                </td>
                <td className="px-4 py-2.5 text-text">{entry.actor_name || "—"}</td>
                <td className="px-4 py-2.5">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-surface-tertiary text-text-secondary font-mono">
                    {entry.action}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-text-secondary truncate max-w-[200px]">
                  {entry.target_type}: {entry.target_id}
                </td>
                <td className="px-4 py-2.5 text-xs text-text-tertiary font-mono">
                  {entry.ip_address}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > 0 && (
        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={total}
          loading={loading}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

function AuthEventsTable({
  entries,
  total,
  page,
  loading,
  onPageChange,
}: {
  entries: { id: string; event_type: string; user_id: string; provider: string; result: string; ip_address: string; created_at: string | null }[];
  total: number;
  page: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-secondary text-text-secondary text-left">
              <th className="px-4 py-2.5 font-medium">Thời gian</th>
              <th className="px-4 py-2.5 font-medium">Người dùng</th>
              <th className="px-4 py-2.5 font-medium">Sự kiện</th>
              <th className="px-4 py-2.5 font-medium">Provider</th>
              <th className="px-4 py-2.5 font-medium">Kết quả</th>
              <th className="px-4 py-2.5 font-medium">IP</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-text-tertiary text-xs">
                  Không có sự kiện
                </td>
              </tr>
            )}
            {entries.map((entry) => (
              <tr
                key={entry.id}
                className="border-t border-border hover:bg-surface-secondary transition-colors"
              >
                <td className="px-4 py-2.5 text-xs text-text-tertiary whitespace-nowrap">
                  {entry.created_at
                    ? new Date(entry.created_at).toLocaleString("vi-VN")
                    : "—"}
                </td>
                <td className="px-4 py-2.5 text-text text-xs truncate max-w-[150px]">
                  {entry.user_id}
                </td>
                <td className="px-4 py-2.5">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-surface-tertiary text-text-secondary font-mono">
                    {entry.event_type}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-text-secondary">{entry.provider}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      entry.result === "success"
                        ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                        : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300"
                    }`}
                  >
                    {entry.result}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-text-tertiary font-mono">
                  {entry.ip_address}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > 0 && (
        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={total}
          loading={loading}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

function PaginationBar({
  page,
  totalPages,
  total,
  loading,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}) {
  const startIdx = page * PAGE_SIZE + 1;
  const endIdx = Math.min((page + 1) * PAGE_SIZE, total);

  return (
    <div className="flex items-center justify-between text-xs text-text-secondary">
      <span>
        {startIdx}–{endIdx} trên {total}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0 || loading}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded border border-border hover:bg-surface-tertiary disabled:opacity-30 transition-colors"
        >
          <ChevronLeft size={12} />
          Trang trước
        </button>
        <span>
          {page + 1} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1 || loading}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded border border-border hover:bg-surface-tertiary disabled:opacity-30 transition-colors"
        >
          Trang sau
          <ChevronRight size={12} />
        </button>
      </div>
    </div>
  );
}
