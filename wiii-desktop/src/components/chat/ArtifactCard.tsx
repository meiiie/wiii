/**
 * ArtifactCard — compact inline card in chat message.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * Shows: icon + title + type badge + language badge + code preview (6 lines).
 * Click → opens ArtifactPanel side panel.
 */
import { memo, useCallback } from "react";
import { Code2, Globe, Table2, BarChart3, FileText, FileSpreadsheet, Maximize2 } from "lucide-react";
import type { ArtifactData, ArtifactType } from "@/api/types";
import { useUIStore } from "@/stores/ui-store";

interface ArtifactCardProps {
  artifact: ArtifactData;
}

const ARTIFACT_ICONS: Record<ArtifactType, typeof Code2> = {
  code: Code2,
  html: Globe,
  react: Code2,
  table: Table2,
  chart: BarChart3,
  document: FileText,
  excel: FileSpreadsheet,
};

const ARTIFACT_LABELS: Record<ArtifactType, string> = {
  code: "Code",
  html: "HTML",
  react: "React",
  table: "Bảng dữ liệu",
  chart: "Biểu đồ",
  document: "Tài liệu",
  excel: "Excel",
};

const MAX_PREVIEW_LINES = 6;

export const ArtifactCard = memo(function ArtifactCard({ artifact }: ArtifactCardProps) {
  const openArtifact = useUIStore((s) => s.openArtifact);
  const Icon = ARTIFACT_ICONS[artifact.artifact_type] || Code2;
  const label = ARTIFACT_LABELS[artifact.artifact_type] || artifact.artifact_type;

  const handleClick = useCallback(() => {
    openArtifact(artifact.artifact_id);
  }, [openArtifact, artifact.artifact_id]);

  // L-1: Split once, reuse
  const lines = artifact.content.split("\n");
  const previewLines = lines.slice(0, MAX_PREVIEW_LINES);
  const hasMore = lines.length > MAX_PREVIEW_LINES;

  return (
    <button
      onClick={handleClick}
      className="w-full text-left my-2 rounded-lg border border-border bg-surface-secondary hover:bg-surface-tertiary transition-colors cursor-pointer group/artifact overflow-hidden"
      aria-label={`Mở artifact: ${artifact.title}`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50">
        <Icon size={16} className="text-[var(--accent)] shrink-0" />
        <span className="text-sm font-medium text-text truncate flex-1">
          {artifact.title}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] font-medium shrink-0">
          {label}
        </span>
        {artifact.language && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-tertiary text-text-secondary font-mono shrink-0">
            {artifact.language}
          </span>
        )}
        <Maximize2
          size={14}
          className="text-text-tertiary opacity-0 group-hover/artifact:opacity-100 transition-opacity shrink-0"
        />
      </div>

      {/* Code preview */}
      {artifact.content && (
        <div className="px-3 py-2 overflow-hidden">
          <pre className="text-xs font-mono text-text-secondary leading-relaxed overflow-hidden">
            <code>
              {previewLines.join("\n")}
              {hasMore && "\n..."}
            </code>
          </pre>
        </div>
      )}

      {/* Execution status indicator — L-3: ARIA role="status" */}
      {artifact.metadata?.execution_status && (
        <div
          className="px-3 py-1.5 border-t border-border/50 flex items-center gap-1.5"
          role="status"
          aria-label={`Trạng thái: ${
            artifact.metadata.execution_status === "success" ? "Đã chạy thành công" :
            artifact.metadata.execution_status === "error" ? "Lỗi thực thi" :
            artifact.metadata.execution_status === "running" ? "Đang chạy" : "Chưa chạy"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              artifact.metadata.execution_status === "success"
                ? "bg-green-500"
                : artifact.metadata.execution_status === "error"
                ? "bg-red-500"
                : artifact.metadata.execution_status === "running"
                ? "bg-amber-500 animate-pulse"
                : "bg-gray-400"
            }`}
          />
          <span className="text-[10px] text-text-tertiary">
            {artifact.metadata.execution_status === "success" && "Đã chạy thành công"}
            {artifact.metadata.execution_status === "error" && "Lỗi thực thi"}
            {artifact.metadata.execution_status === "running" && "Đang chạy..."}
            {artifact.metadata.execution_status === "pending" && "Chưa chạy"}
          </span>
        </div>
      )}
    </button>
  );
});
