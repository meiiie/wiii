/**
 * OrgManagerKnowledge — Sprint 190: "Kho Tri Thức"
 *
 * 5th tab in OrgAdminView. Org admins can upload, list, and
 * delete PDF documents for their organization's knowledge base.
 *
 * Uses org-admin-store for state management (consistent with Members/Settings tabs).
 */
import { useEffect, useRef, useState } from "react";
import { FileUp, Trash2, FileText, RefreshCw, AlertCircle, CheckCircle2, Loader2, Upload } from "lucide-react";
import { useOrgAdminStore } from "@/stores/org-admin-store";
import type { OrgDocument } from "@/api/types";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { KnowledgeVisualizer } from "./KnowledgeVisualizer";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  uploading: {
    label: "Đang tải lên",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    icon: <Loader2 size={12} className="animate-spin" />,
  },
  processing: {
    label: "Đang xử lý",
    color: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    icon: <Loader2 size={12} className="animate-spin" />,
  },
  ready: {
    label: "Sẵn sàng",
    color: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    icon: <CheckCircle2 size={12} />,
  },
  failed: {
    label: "Lỗi",
    color: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    icon: <AlertCircle size={12} />,
  },
};

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  try {
    return new Date(dateStr).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function OrgManagerKnowledge({ orgId }: { orgId: string }) {
  const {
    documents,
    documentsTotal,
    documentsLoading,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    showToast,
  } = useOrgAdminStore();

  const [uploading, setUploading] = useState(false);
  const [uploadingFile, setUploadingFile] = useState<File | null>(null);
  const [uploadStage, setUploadStage] = useState<"sending" | "processing">("sending");
  const [deleteTarget, setDeleteTarget] = useState<OrgDocument | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup stageTimerRef on unmount (if component unmounts mid-upload)
  useEffect(() => {
    return () => {
      if (stageTimerRef.current) {
        clearTimeout(stageTimerRef.current);
        stageTimerRef.current = null;
      }
    };
  }, []);

  // Fetch document list on mount
  useEffect(() => {
    fetchDocuments(orgId);
  }, [orgId, fetchDocuments]);

  // Auto-refresh while documents are processing
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === "uploading" || d.status === "processing");
    if (hasProcessing) {
      refreshTimerRef.current = setInterval(() => fetchDocuments(orgId), 5000);
    }
    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [documents, orgId, fetchDocuments]);

  // Handle file upload — Sprint 213: two-stage progress indicator
  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showToast("error", "Chỉ chấp nhận file PDF");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      showToast("error", `File quá lớn (${formatFileSize(file.size)}). Tối đa 50MB.`);
      return;
    }

    setUploading(true);
    setUploadingFile(file);
    setUploadStage("sending");
    stageTimerRef.current = setTimeout(() => setUploadStage("processing"), 1500);
    try {
      await uploadDocument(orgId, file);
    } finally {
      setUploading(false);
      setUploadingFile(null);
      if (stageTimerRef.current) {
        clearTimeout(stageTimerRef.current);
        stageTimerRef.current = null;
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteDocument(orgId, deleteTarget.document_id);
    setDeleteTarget(null);
  };

  if (documentsLoading && documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-text-secondary">
        <Loader2 size={20} className="animate-spin mr-2" />
        Đang tải...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Upload area */}
      <div
        className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
          dragOver
            ? "border-[var(--accent)] bg-[var(--accent)]/5"
            : "border-border hover:border-[var(--accent)]/50"
        } ${uploading ? "opacity-50 pointer-events-none" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        aria-label="Khu vực tải lên tài liệu PDF"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click(); }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          className="hidden"
          aria-hidden="true"
        />
        {uploading && uploadingFile ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 size={32} className="text-[var(--accent)] animate-spin" />
            <p className="text-sm font-medium text-text truncate max-w-[90%]" title={uploadingFile.name}>
              {uploadingFile.name}
            </p>
            <p className="text-xs text-text-tertiary">{formatFileSize(uploadingFile.size)}</p>
            <p className="text-sm text-text-secondary">
              {uploadStage === "sending"
                ? "Đang gửi file lên máy chủ..."
                : "Đang phân tích và tạo embedding..."}
            </p>
            {/* 2-step dot indicator */}
            <div className="flex items-center gap-1 text-xs text-text-tertiary">
              <span className={`w-2 h-2 rounded-full ${uploadStage === "sending" ? "bg-[var(--accent)]" : "bg-[var(--accent)]"}`} />
              <span className={`w-6 h-0.5 ${uploadStage === "processing" ? "bg-[var(--accent)]" : "bg-border"}`} />
              <span className={`w-2 h-2 rounded-full ${uploadStage === "processing" ? "bg-[var(--accent)]" : "bg-border"}`} />
              <span className="ml-2">
                {uploadStage === "sending" ? "Tải lên" : "Xử lý"}
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={32} className="text-text-tertiary" />
            <p className="text-sm font-medium text-text">
              Kéo thả file PDF vào đây hoặc nhấn để chọn
            </p>
            <p className="text-xs text-text-tertiary">
              Chỉ chấp nhận file PDF, tối đa 50MB
            </p>
          </div>
        )}
      </div>

      {/* Header with count + refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text">
          Tài liệu ({documentsTotal})
        </h3>
        <button
          onClick={() => fetchDocuments(orgId)}
          className="p-1.5 rounded-lg hover:bg-surface-tertiary transition-colors text-text-secondary"
          aria-label="Làm mới danh sách"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Document list */}
      {documents.length === 0 ? (
        <div className="text-center py-8 text-text-tertiary text-sm">
          <FileText size={32} className="mx-auto mb-2 opacity-50" />
          Chưa có tài liệu nào. Tải lên file PDF để bắt đầu.
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => {
            const cfg = STATUS_CONFIG[doc.status] || STATUS_CONFIG.failed;
            return (
              <div
                key={doc.document_id}
                className="relative overflow-hidden flex items-center gap-3 p-3 rounded-xl border border-border bg-surface hover:bg-surface-secondary transition-colors"
              >
                <FileUp size={18} className="text-text-tertiary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-text truncate" title={doc.filename}>
                    {doc.filename}
                  </p>
                  <div className="flex items-center gap-3 text-xs text-text-tertiary mt-0.5">
                    <span>{formatFileSize(doc.file_size_bytes)}</span>
                    {doc.page_count !== null && <span>{doc.page_count} trang</span>}
                    {doc.chunk_count !== null && doc.chunk_count > 0 && (
                      <span>{doc.chunk_count} phân đoạn</span>
                    )}
                    <span>{formatDate(doc.created_at)}</span>
                  </div>
                  {doc.error_message && (
                    <p className="text-xs text-red-500 mt-1 truncate" title={doc.error_message}>
                      {doc.error_message}
                    </p>
                  )}
                </div>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                  {cfg.icon}
                  {cfg.label}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(doc); }}
                  className="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors text-text-tertiary hover:text-red-600"
                  aria-label={`Xoá tài liệu ${doc.filename}`}
                >
                  <Trash2 size={14} />
                </button>
                {/* Sprint 213: Indeterminate progress bar for uploading/processing docs */}
                {(doc.status === "uploading" || doc.status === "processing") && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-border">
                    <div className="h-full w-1/3 bg-[var(--accent)] animate-progress-bar rounded-full" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          open={true}
          title="Xoá tài liệu"
          message={`Bạn có chắc muốn xoá "${deleteTarget.filename}"? Toàn bộ dữ liệu embedding sẽ bị xoá.`}
          confirmLabel="Xoá"
          variant="danger"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {/* Knowledge Visualization — Sprint 191 */}
      <KnowledgeVisualizer orgId={orgId} hasDocuments={documents.length > 0} />
    </div>
  );
}
