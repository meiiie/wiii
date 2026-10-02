import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { useNekoSessionStore } from "../stores/neko-session-store";

interface SessionDeleteDialogProps {
  target: { id: string; title: string };
  opener: HTMLElement | null;
  fallbackFocusRef: RefObject<HTMLButtonElement>;
  onCancel: () => void;
  onDeleted: () => void;
}

export function SessionDeleteDialog({ target, opener, fallbackFocusRef, onCancel, onDeleted }: SessionDeleteDialogProps) {
  const session = useNekoSessionStore((state) => state.sessions[target.id]);
  const deleteSession = useNekoSessionStore((state) => state.deleteSession);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pendingRef = useRef(false);
  const mountedRef = useRef(true);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const wasBusyRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const taskScopeWarningId = useId();
  const hasTaskScope = session?.taskScope !== undefined;
  const busy = pending || session?.deletePending === true;

  useEffect(() => {
    mountedRef.current = true;
    const dialog = dialogRef.current;
    dialog?.showModal();
    cancelRef.current?.focus();
    return () => {
      mountedRef.current = false;
      dialog?.close();
      queueMicrotask(() => {
        const destination = opener?.isConnected ? opener : fallbackFocusRef.current;
        if (destination?.isConnected) destination.focus();
      });
    };
  }, [opener, fallbackFocusRef]);

  useEffect(() => {
    if (busy) dialogRef.current?.focus();
    else if (wasBusyRef.current) cancelRef.current?.focus();
    wasBusyRef.current = busy;
  }, [busy]);

  const dismiss = () => {
    if (!pendingRef.current && !useNekoSessionStore.getState().sessions[target.id]?.deletePending) onCancel();
  };

  const confirm = async () => {
    const current = useNekoSessionStore.getState().sessions[target.id];
    if (pendingRef.current || current?.deletePending || !current) return;
    pendingRef.current = true;
    setPending(true);
    setError(null);
    let failure: string | null = null;
    try {
      await deleteSession(target.id);
    } catch (cause) {
      failure = cause instanceof Error ? cause.message : String(cause);
    }
    if (!mountedRef.current) return;
    const remaining = useNekoSessionStore.getState().sessions[target.id];
    if (!remaining) {
      onDeleted();
      return;
    }
    pendingRef.current = false;
    setPending(false);
    setError(failure || (remaining.status === "error" ? remaining.statusDetail : null) || "Hãy thử lại hoặc hủy để giữ phiên.");
  };

  return (
    <dialog
      ref={dialogRef}
      tabIndex={-1}
      aria-labelledby={titleId}
      aria-describedby={hasTaskScope ? `${descriptionId} ${taskScopeWarningId}` : descriptionId}
      aria-busy={busy}
      className="fixed inset-0 m-0 h-full max-h-none w-full max-w-none overflow-y-auto border-0 bg-transparent p-0"
      onCancel={(event) => { event.preventDefault(); dismiss(); }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          dismiss();
        }
        if (event.key !== "Tab") return;
        const items = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)")];
        const first = items[0];
        const last = items[items.length - 1];
        if (!first) {
          event.preventDefault();
          event.currentTarget.focus();
        } else if (event.shiftKey ? document.activeElement === first || document.activeElement === event.currentTarget : document.activeElement === last || document.activeElement === event.currentTarget) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        }
      }}
    >
      <div className="grid min-h-full place-items-center bg-[rgba(29,27,24,0.3)] p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) dismiss(); }}>
        <section className="min-w-0 w-full max-w-[440px] rounded-2xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-5 text-[var(--nk-text)] shadow-[0_24px_80px_rgba(29,27,24,0.2)]" data-testid="session-delete-dialog">
          <div className="flex items-start gap-3">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-[var(--nk-danger)]" />
            <div className="min-w-0 flex-1">
              <h1 id={titleId} className="text-[17px] font-semibold">Xóa lịch sử phiên?</h1>
              <p id={descriptionId} className="mt-2 text-[13px] leading-5 text-[var(--nk-text-2)]">Xóa sẽ dừng runtime của phiên và xóa lịch sử đã lưu trong Wiii. Nếu chỉ muốn đóng runtime và giữ lịch sử, hãy hủy rồi chọn Kết thúc phiên.</p>
            </div>
          </div>
          <div className="mt-4 min-w-0 rounded-lg border border-[var(--nk-border)] bg-[var(--nk-raised)] px-3 py-2.5">
            <p className="whitespace-pre-wrap break-words text-[13px] font-medium [overflow-wrap:anywhere]" data-testid="session-delete-title">{target.title}</p>
            <p className="mt-1 break-all font-mono text-[10px] leading-4 text-[var(--nk-text-3)]">ID: {target.id}</p>
          </div>
          <p className="mt-3 text-[12px] leading-5 text-[var(--nk-text-3)]">Không thể hoàn tác. Tệp trong thư mục dự án vẫn được giữ nguyên.</p>
          {hasTaskScope ? (
            <p id={taskScopeWarningId} role="note" data-testid="session-delete-task-scope-warning" className="mt-3 rounded-lg border border-[var(--nk-border)] bg-[var(--nk-raised)] px-3 py-2 text-[12px] leading-5 text-[var(--nk-text-2)]">
              Xóa cũng xóa liên kết tác vụ và receipt đã lưu trong Wiii (nếu có). Liên kết này có thể cần để đối soát hoặc tiếp tục tác vụ, nhất là khi kết quả chưa được xác nhận. Thao tác này không xóa checkpoint hoặc writer lock của Neko. Wiii không giữ lại lịch sử hay liên kết này sau khi xóa.
            </p>
          ) : null}
          {busy ? <p role="status" className="mt-3 flex items-center gap-2 text-[12px] leading-5 text-[var(--nk-text-2)]"><LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 shrink-0 animate-spin" />Đang dừng runtime và xóa lịch sử…</p> : null}
          {!session ? <p role="status" className="mt-3 text-[12px] leading-5 text-[var(--nk-text-2)]">Phiên này không còn trong danh sách. Không có phiên khác bị xóa.</p> : null}
          {error ? <p role="alert" className="mt-3 whitespace-pre-wrap break-words rounded-lg bg-[var(--nk-danger-soft)] px-3 py-2 text-[12px] leading-5 text-[var(--nk-text)] [overflow-wrap:anywhere]">Chưa xóa được phiên. Lịch sử vẫn được giữ. {error}</p> : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <button ref={cancelRef} type="button" disabled={busy} onClick={dismiss} className="min-h-9 rounded-lg border border-[var(--nk-border)] px-3 text-[12px] font-medium text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] disabled:opacity-50">Hủy</button>
            <button type="button" disabled={busy || !session} onClick={() => void confirm()} className="min-h-9 rounded-lg bg-[var(--nk-danger)] px-3 text-[12px] font-medium text-[var(--nk-on-inverse)] hover:opacity-90 disabled:opacity-50">{busy ? "Đang xóa…" : "Xóa phiên và lịch sử"}</button>
          </div>
        </section>
      </div>
    </dialog>
  );
}
