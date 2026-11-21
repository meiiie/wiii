/**
 * Inline permission gate (FR-006) — waku-fidelity card: quiet raised surface,
 * reject stays the prominent default (fail-closed by design), allow is
 * the bordered secondary.
 */
import { useId } from "react";
import { ShieldCheck } from "lucide-react";
import type { PermissionRequest } from "../drivers/types";
import {
  buildPermissionPreview,
  permissionOptionScope,
  permissionPreviewIsTruncated,
  permissionPreviewText,
  type PermissionPreviewSession,
} from "./permission-preview";

interface PermissionCardProps {
  request: PermissionRequest;
  onResolve: (optionId: string | null) => void;
  resolving?: boolean;
  blockedByCancel?: boolean;
  session?: PermissionPreviewSession;
}

export function PermissionCard({
  request,
  onResolve,
  resolving = false,
  blockedByCancel = false,
  session,
}: PermissionCardProps) {
  const scopeId = useId();
  const preview = buildPermissionPreview(request, session);
  const previewTruncated = preview.truncated || permissionPreviewIsTruncated(request.title)
    || request.options.some((option) => permissionPreviewIsTruncated(option.label, 160));
  const allows = request.options.filter((o) => o.kind.startsWith("allow"));
  const rejects = request.options.filter((o) => !o.kind.startsWith("allow"));
  const busy = resolving || blockedByCancel;
  const busyLabel = resolving
    ? "Đang lưu quyết định…"
    : blockedByCancel
      ? "Đang lưu yêu cầu dừng…"
      : "";

  return (
    <div
      className="my-2 min-w-0 rounded-[10px] border border-[var(--nk-border-strong)] bg-[var(--nk-raised)] px-4 py-3 [overflow-wrap:anywhere]"
      data-testid="permission-card"
      aria-busy={busy}
    >
      <p className="flex items-center gap-2 text-[12px] font-medium text-[var(--nk-text-2)]">
        <ShieldCheck aria-hidden="true" className="h-4 w-4 text-[var(--nk-warning)]" />
        Cần bạn duyệt
      </p>
      <p className="mb-3 mt-1 text-[13px] text-[var(--nk-text)]">
        {permissionPreviewText(request.title) ?? "Yêu cầu quyền chưa có mô tả."}
      </p>
      <div className="mb-3 min-w-0 rounded-lg border border-[var(--nk-border)] px-3 py-2.5 text-[11.5px] leading-5 text-[var(--nk-text-2)]" data-testid="permission-preview">
        {preview.source === "missing" ? (
          <p>Chưa có thông tin thao tác.</p>
        ) : (
          <dl className="grid gap-2 sm:grid-cols-2">
            <div>
              <dt className="text-[var(--nk-text-3)]">{preview.toolName ? "Công cụ" : "Hoạt động"}</dt>
              <dd>{preview.toolName ?? preview.title ?? "Chưa được agent cung cấp."}</dd>
            </div>
            {preview.operation ? <div><dt className="text-[var(--nk-text-3)]">Thao tác</dt><dd>{preview.operation}</dd></div> : null}
            <div>
              <dt className="text-[var(--nk-text-3)]">Mục tiêu</dt>
              <dd>
                {preview.targets.length ? (
                  <ul className="v3-space-y-1">
                    {preview.targets.map((target, index) => (
                      <li key={index} className="min-w-0 font-mono text-[11px]">
                        {target.path}{target.line ? ` · dòng ${target.line}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : "Chưa có mục tiêu."}
              </dd>
            </div>
            {preview.detail ? <div className="sm:col-span-2"><dt className="text-[var(--nk-text-3)]">Chi tiết</dt><dd className="whitespace-pre-wrap">{preview.detail}</dd></div> : null}
          </dl>
        )}
        {previewTruncated ? <p className="mt-2 text-[var(--nk-text-3)]">Bản xem trước đã rút gọn.</p> : null}
      </div>
      <div className="flex flex-wrap items-start gap-1.5">
        {rejects.map((option, index) => (
          <div key={option.optionId} className="min-w-0 max-w-full">
            <button
              type="button"
              className="max-w-full rounded-lg bg-[var(--nk-inverse)] px-3 py-1.5 text-left text-[12px] font-medium text-[var(--nk-on-inverse)] transition-opacity hover:opacity-90 aria-disabled:cursor-wait aria-disabled:opacity-50 aria-disabled:hover:opacity-50"
              aria-disabled={busy}
              aria-describedby={`${scopeId}-reject-${index}`}
              onClick={() => {
                if (!busy) onResolve(option.optionId);
              }}
            >
              {permissionPreviewText(option.label, 160) ?? "Lựa chọn chưa có nhãn."}
            </button>
            <p id={`${scopeId}-reject-${index}`} className="mt-1 max-w-[240px] text-[10.5px] leading-4 text-[var(--nk-text-3)]">{permissionOptionScope(option.kind)}</p>
          </div>
        ))}
        {allows.map((option, index) => (
          <div key={option.optionId} className="min-w-0 max-w-full">
            <button
              type="button"
              className="max-w-full rounded-lg border border-[var(--nk-border-strong)] px-3 py-1.5 text-left text-[12px] text-[var(--nk-text-2)] transition-colors hover:bg-[var(--nk-overlay)] hover:text-[var(--nk-text)] aria-disabled:cursor-wait aria-disabled:opacity-50 aria-disabled:hover:bg-transparent aria-disabled:hover:text-[var(--nk-text-2)]"
              aria-disabled={busy}
              aria-describedby={`${scopeId}-allow-${index}`}
              onClick={() => {
                if (!busy) onResolve(option.optionId);
              }}
            >
              {permissionPreviewText(option.label, 160) ?? "Lựa chọn chưa có nhãn."}
            </button>
            <p id={`${scopeId}-allow-${index}`} className="mt-1 max-w-[240px] text-[10.5px] leading-4 text-[var(--nk-text-3)]">{permissionOptionScope(option.kind)}</p>
          </div>
        ))}
      </div>
      <p
        className={busy
          ? "mt-2 text-[11px] text-[var(--nk-text-3)]"
          : "sr-only"}
        role="status"
        aria-live="polite"
      >
        {busyLabel}
      </p>
    </div>
  );
}
