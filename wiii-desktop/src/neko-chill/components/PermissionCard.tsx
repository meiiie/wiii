/**
 * Inline permission gate (FR-006) — waku-fidelity card: quiet raised surface,
 * single-use decisions are primary; session-wide choices are disclosed.
 * No selection or dismissal ever implicitly approves.
 */
import { useId } from "react";
import { ShieldCheck } from "lucide-react";
import type { PermissionOption, PermissionRequest } from "../drivers/types";
import {
  buildPermissionPreview,
  permissionCodeText,
  permissionOptionLabel,
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
  const once = request.options.filter((option) => option.kind === "allow_once" || option.kind === "reject_once");
  const mainOptions = once.length ? once : request.options;
  const moreOptions = once.length ? request.options.filter((option) => !once.includes(option)) : [];
  const busy = resolving || blockedByCancel;
  const fileAction = ({ write_file: "Ghi tệp", edit: "Sửa tệp", multi_edit: "Sửa tệp" } as Record<string, string>)[preview.toolName ?? ""];
  const busyLabel = resolving
    ? "Đang lưu quyết định…"
    : blockedByCancel
      ? "Đang lưu yêu cầu dừng…"
      : "";
  const choice = (option: PermissionOption) => {
    const index = request.options.indexOf(option);
    const primary = option.kind === "allow_once";
    const scope = permissionOptionScope(option);
    return <div key={option.optionId} className="min-w-0 max-w-full">
      <button type="button"
        className={`max-w-full rounded-lg px-3 py-1.5 text-left text-[12px] transition-opacity hover:opacity-80 aria-disabled:cursor-wait aria-disabled:opacity-50 ${primary
          ? "bg-[var(--nk-inverse)] font-medium text-[var(--nk-on-inverse)]"
          : "text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)]"}`}
        aria-disabled={busy} aria-describedby={`${scopeId}-option-${index}`}
        onClick={() => { if (!busy) onResolve(option.optionId); }}>
        {permissionOptionLabel(option) ?? "Lựa chọn chưa có nhãn."}
      </button>
      <p id={`${scopeId}-option-${index}`} className={scope === "Phạm vi do agent quyết định" || scope === "Chưa rõ phạm vi" ? "mt-1 text-[10.5px] text-[var(--nk-text-3)]" : "sr-only"}>{scope}</p>
    </div>;
  };

  return (
    <div
      className="my-2 min-w-0 rounded-[10px] border border-[var(--nk-border-strong)] bg-[var(--nk-raised)] px-4 py-3 [overflow-wrap:anywhere]"
      data-testid="permission-card"
      aria-busy={busy}
    >
      <p className="flex items-center gap-2 text-[12px] font-medium text-[var(--nk-text-2)]">
        <ShieldCheck aria-hidden="true" className="h-4 w-4 text-[var(--nk-warning)]" />
        {fileAction ? `${fileAction} · cần duyệt` : "Cần bạn duyệt"}
      </p>
      {!fileAction && <p className="mb-3 mt-1 text-[13px] text-[var(--nk-text)]">
        {permissionPreviewText(request.title) ?? "Yêu cầu quyền chưa có mô tả."}
      </p>}
      <div className="mb-3 mt-2 min-w-0 rounded-lg border border-[var(--nk-border)] px-3 py-2.5 text-[11.5px] leading-5 text-[var(--nk-text-2)]" data-testid="permission-preview">
        {preview.source === "request" ? (
          <div className="min-w-0 space-y-2">
            {preview.targets.map((target, index) => <p key={index} className="font-mono text-[11px]">{target.path}</p>)}
            {preview.changes?.length ? preview.changes.map((change, index) => (
              <div key={index} className="min-w-0">
                {change.path && <p className="mb-1 font-mono text-[11px]">{permissionPreviewText(change.path, 320)}</p>}
                <div className="max-h-52 overflow-auto rounded border border-[var(--nk-border)] bg-[var(--nk-base)]" tabIndex={0} role="region" aria-label={change.before !== undefined ? "Thay đổi sắp ghi" : "Nội dung sắp ghi"}>
                  {change.before !== undefined && <>
                    <p className="px-2.5 pt-1 text-[10px] text-[var(--nk-text-3)]">− Trước</p>
                    <pre dir="ltr" aria-label="Nội dung cũ" className="whitespace-pre-wrap break-words border-b border-[var(--nk-border)] bg-red-500/5 px-2.5 py-2 font-mono text-[11px] text-[var(--nk-text-2)]">{permissionCodeText(change.before) || (change.beforeTruncated ? "(Đã rút gọn)" : "(Trống)")}{change.beforeTruncated && change.before ? "\n…" : ""}</pre>
                    <p className="px-2.5 pt-1 text-[10px] text-[var(--nk-text-3)]">+ Sau</p>
                  </>}
                  <pre dir="ltr" aria-label="Nội dung mới" className={`whitespace-pre-wrap break-words px-2.5 py-2 font-mono text-[11px] text-[var(--nk-text)] ${change.before !== undefined ? "bg-green-500/5" : ""}`}>{permissionCodeText(change.after) || (change.afterTruncated ? "(Đã rút gọn)" : change.before !== undefined ? "(Xoá đoạn này)" : "(Tệp trống)")}{change.afterTruncated && change.after ? "\n…" : ""}</pre>
                </div>
              </div>
            )) : <p>{fileAction ? "Agent chưa gửi nội dung thay đổi." : permissionPreviewText(request.title)}</p>}
          </div>
        ) : preview.source === "missing" ? (
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
      <div role="group" aria-label="Quyết định" className="flex flex-wrap items-center gap-1.5">
        {mainOptions.filter(option => option.kind === "allow_once").map(choice)}
        {mainOptions.filter(option => option.kind !== "allow_once").map(choice)}
      </div>
      {moreOptions.length > 0 && <details key={request.requestId} className="mt-2 text-[11px] text-[var(--nk-text-3)]">
        <summary className="w-fit cursor-pointer rounded py-1 hover:text-[var(--nk-text-2)]">Thêm lựa chọn</summary>
        <div className="mt-1 flex flex-wrap gap-1.5 border-t border-[var(--nk-border)] pt-2">{moreOptions.map(choice)}</div>
      </details>}
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
