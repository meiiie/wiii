/**
 * GDPR tab — Export/Forget with confirmation.
 * Sprint 179: "Quản Trị Toàn Diện"
 */
import { useState } from "react";
import { Download, Trash2, AlertTriangle, CheckCircle } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";

export function GdprTab() {
  const { loading, error, gdprExportResult, gdprForgetResult, gdprExport, gdprForget } =
    useAdminStore();
  const [userId, setUserId] = useState("");
  const [showForgetConfirm, setShowForgetConfirm] = useState(false);

  const handleExport = async () => {
    if (!userId.trim()) return;
    await gdprExport(userId.trim());
  };

  const handleForget = async () => {
    if (!userId.trim()) return;
    setShowForgetConfirm(false);
    await gdprForget(userId.trim());
  };

  const handleDownload = () => {
    if (!gdprExportResult) return;
    const blob = new Blob(
      [JSON.stringify(gdprExportResult.data, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gdpr-export-${gdprExportResult.user_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="text-sm font-medium text-text">Tuân thủ GDPR</div>
        <div className="text-xs text-text-tertiary">
          Xuất hoặc xoá dữ liệu người dùng theo yêu cầu
        </div>
      </div>

      {/* User ID input */}
      <div>
        <label className="block text-sm font-medium text-text-secondary mb-1.5">
          Mã người dùng
        </label>
        <input
          type="text"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="Nhập UUID của người dùng..."
          className="w-full px-3 py-2 rounded-lg border border-border bg-surface-secondary text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        />
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={handleExport}
          disabled={!userId.trim() || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-tertiary transition-colors disabled:opacity-50"
        >
          <Download size={14} />
          Xuất dữ liệu
        </button>
        <button
          onClick={() => setShowForgetConfirm(true)}
          disabled={!userId.trim() || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-red-300 dark:border-red-800 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors disabled:opacity-50"
        >
          <Trash2 size={14} />
          Xoá dữ liệu
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 text-sm">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {/* Export result */}
      {gdprExportResult && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-300">
              <CheckCircle size={14} />
              Xuất dữ liệu thành công — {gdprExportResult.exported_at}
            </div>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-surface-tertiary transition-colors"
            >
              <Download size={12} />
              Tải JSON
            </button>
          </div>
          <pre className="p-4 rounded-lg bg-surface-secondary border border-border text-xs text-text overflow-auto max-h-[300px] font-mono">
            {JSON.stringify(gdprExportResult.data, null, 2)}
          </pre>
        </div>
      )}

      {/* Forget result */}
      {gdprForgetResult && (
        <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-green-700 dark:text-green-300">
            <CheckCircle size={14} />
            Dữ liệu đã được xoá
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-green-600 dark:text-green-400">
            <span>Hồ sơ ẩn danh: {gdprForgetResult.profile_anonymized ? "Có" : "Không"}</span>
            <span>Danh tính xoá: {gdprForgetResult.identities_deleted}</span>
            <span>Tokens thu hồi: {gdprForgetResult.tokens_revoked}</span>
            <span>Ký ức xoá: {gdprForgetResult.memories_deleted}</span>
          </div>
          <div className="text-[11px] text-text-tertiary">
            Nhật ký kiểm toán được giữ lại theo yêu cầu pháp lý.
          </div>
        </div>
      )}

      {/* Forget confirmation */}
      <ConfirmDialog
        open={showForgetConfirm}
        title="Xoá dữ liệu người dùng?"
        message={`Thao tác này không thể hoàn tác. Tất cả dữ liệu cá nhân của user "${userId}" sẽ bị xoá vĩnh viễn. Nhật ký kiểm toán sẽ được giữ lại.`}
        confirmLabel="Xoá vĩnh viễn"
        cancelLabel="Huỷ"
        variant="danger"
        onConfirm={handleForget}
        onCancel={() => setShowForgetConfirm(false)}
      />
    </div>
  );
}
