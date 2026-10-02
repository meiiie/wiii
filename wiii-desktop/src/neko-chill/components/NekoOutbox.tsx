import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, ListOrdered, LoaderCircle, Pause, Pencil, Play, X } from "lucide-react";
import { hydrateOutbox, outbox, useNekoOutboxStore } from "../stores/neko-outbox-store";

const iconButton = "grid h-8 w-8 shrink-0 place-items-center rounded-md text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--nk-accent)] disabled:cursor-not-allowed disabled:opacity-40";

/** Compact presentation of durable intent. All delivery decisions stay in the outbox. */
export function NekoOutbox({ sessionId }: { sessionId: string }) {
  const queue = useNekoOutboxStore(state => state.snapshot.queues.find(q => q.sessionId === sessionId));
  const error = useNekoOutboxStore(state => state.error);
  const ready = useNekoOutboxStore(state => state.ready);
  const listId = useId();
  const [expanded, setExpanded] = useState(true);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const headingRef = useRef<HTMLButtonElement>(null);
  const editTriggerRef = useRef<HTMLButtonElement | null>(null);
  const focusAfterAction = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!pending && !editingId && focusAfterAction.current) {
      focusAfterAction.current.focus();
      focusAfterAction.current = null;
    }
  }, [pending, editingId]);
  const editing = queue?.items.some(item => item.id === editingId) ?? false;
  const uncertain = queue?.items.some(item => item.state === "uncertain") ?? false;
  const delivering = queue?.items.some(item => item.state === "delivering") ?? false;

  async function run(action: () => Promise<void>, after?: () => void) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(true);
    setActionError(null);
    try { await action(); after?.(); }
    catch (failure) { setActionError(String(failure)); }
    finally { pendingRef.current = false; setPending(false); }
  }
  function finishEditing() {
    setEditingId(null);
    setDraft("");
    focusAfterAction.current = editTriggerRef.current;
  }

  if (!error && !queue?.items.length) return null;
  const status = uncertain ? "Cần kiểm tra" : queue?.paused ? "Tạm dừng" : delivering ? "Đang gửi" : "Chờ gửi";
  const resumeBlocked = pending || editing || uncertain || delivering;
  const resumeHint = editing ? "Lưu hoặc hủy sửa trước khi tiếp tục"
    : uncertain ? "Đối chiếu lịch sử rồi bỏ tin chưa rõ kết quả khỏi hàng đợi"
    : delivering ? "Chờ tin đang gửi hoàn tất" : "Gửi lần lượt khi phiên sẵn sàng";

  return (
    <section aria-label="Hàng đợi tin nhắn" className="relative mx-auto -mb-3 w-full max-w-[780px] overflow-hidden rounded-t-[14px] border border-[var(--nk-border)] bg-[var(--nk-inset)] pb-3 text-[var(--nk-text)]" data-testid="neko-outbox">
      {(error || actionError) && <p role="alert" className="px-3 py-2 text-[12px] text-[var(--nk-danger)]">{actionError || error}</p>}
      {!ready && <button type="button" className="px-3 py-2 text-[12px] underline" onClick={() => void run(hydrateOutbox)} disabled={pending}>Thử đọc lại hàng đợi</button>}
      {queue && queue.items.length > 0 && <>
        <div className="flex min-h-10 items-center gap-1 px-2">
          <button ref={headingRef} type="button" aria-expanded={expanded} aria-controls={listId}
            aria-label={`${expanded ? "Thu gọn" : "Mở"} hàng đợi, ${queue.items.length} tin, ${status.toLowerCase()}`}
            disabled={editing || pending} onClick={() => setExpanded(value => !value)}
            className="flex min-h-8 min-w-0 flex-1 items-center gap-2 rounded-md px-1 text-left text-[12px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--nk-accent)]">
            <ListOrdered size={14} aria-hidden="true" className="shrink-0 text-[var(--nk-text-2)]" />
            <span className="shrink-0 font-medium">Hàng đợi</span>
            <span className="rounded bg-[var(--nk-overlay)] px-1.5 text-[11px] tabular-nums">{queue.items.length}</span>
            <span className="truncate text-[11px] text-[var(--nk-text-2)]">{status}</span>
            <ChevronDown size={13} aria-hidden="true" className={`ml-auto shrink-0 ${expanded ? "" : "-rotate-90"}`} />
          </button>
          <button type="button" className={iconButton} aria-label={queue.paused ? "Tiếp tục hàng đợi" : "Tạm dừng hàng đợi"}
            title={queue.paused ? resumeHint : "Tạm dừng hàng đợi; lượt đang chạy vẫn tiếp tục"}
            disabled={queue.paused ? resumeBlocked : pending || editing}
            onClick={() => void run(() => queue.paused ? outbox.resume(sessionId) : outbox.pause(sessionId, "Bạn đã tạm dừng hàng đợi."))}>
            {pending ? <LoaderCircle size={14} aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
              : queue.paused ? <Play size={14} aria-hidden="true" /> : <Pause size={14} aria-hidden="true" />}
          </button>
        </div>
        <span role="status" aria-live="polite" className="sr-only">{queue.items.length} tin trong hàng đợi. {status}.</span>
        {(queue.paused || uncertain) && <p className="px-3 pb-2 text-[11px] leading-4 text-[var(--nk-text-2)]">
          {uncertain ? "Có tin chưa rõ kết quả. Đối chiếu lịch sử trước khi bỏ khỏi hàng đợi; Wiii không tự gửi lại."
            : editing ? "Đang sửa tin chờ. Lưu hoặc hủy sửa rồi chọn tiếp tục."
              : queue.reason || "Tin chờ được giữ lại. Chọn tiếp tục khi sẵn sàng."}
        </p>}
        <ol id={listId} hidden={!expanded} className="max-h-[min(28vh,200px)] overflow-y-auto overscroll-contain px-2 pb-1" aria-label="Các tin chờ theo thứ tự gửi">
          {queue.items.map((item, index) => {
            const isEditing = editingId === item.id;
            const preview = previewId === item.id;
            return <li key={item.id} className="rounded-lg hover:bg-[var(--nk-overlay)] focus-within:bg-[var(--nk-overlay)]" data-testid="neko-outbox-row">
              <div className="flex min-h-9 items-center gap-1">
                <span className="w-5 shrink-0 text-center text-[11px] tabular-nums text-[var(--nk-text-2)]" aria-label={`Tin ${index + 1}`}>
                  {item.state === "delivering" ? <LoaderCircle size={13} aria-label="Đang gửi" className="mx-auto animate-spin motion-reduce:animate-none" /> : index + 1}
                </span>
                <button type="button" className="min-w-0 flex-1 truncate rounded px-1 py-2 text-left text-[12px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--nk-accent)]"
                  title={item.text} aria-label={`Xem tin ${index + 1}: ${item.text}`} aria-expanded={preview || isEditing}
                  disabled={isEditing} onClick={() => setPreviewId(preview ? null : item.id)}>{item.text}</button>
                {item.state === "queued" && <button type="button" className={iconButton} aria-label={`Sửa tin ${index + 1}`} title="Sửa tin chờ"
                  disabled={pending || editing} onClick={event => {
                    editTriggerRef.current = event.currentTarget;
                    void run(() => outbox.pause(sessionId, "Hàng đợi tạm dừng sau khi sửa. Chọn tiếp tục khi sẵn sàng."), () => {
                      setDraft(item.text); setEditingId(item.id); setPreviewId(null);
                    });
                  }}><Pencil size={13} aria-hidden="true" /></button>}
                <button type="button" className={iconButton} aria-label={`Bỏ tin ${index + 1} khỏi hàng đợi`} title="Bỏ khỏi hàng đợi; lịch sử phiên vẫn được giữ"
                  disabled={pending || editing || item.state === "delivering"}
                  onClick={() => void run(() => outbox.remove(sessionId, item.id), () => { focusAfterAction.current = headingRef.current; })}><X size={14} aria-hidden="true" /></button>
              </div>
              {item.state === "uncertain" && <p className="px-6 pb-1 text-[11px] text-[var(--nk-text-2)]">Chưa rõ kết quả gửi</p>}
              {preview && !isEditing && <p className="whitespace-pre-wrap px-6 pb-2 text-[12px] leading-5 [overflow-wrap:anywhere]">{item.text}</p>}
              {isEditing && <div className="px-2 pb-2">
                <textarea autoFocus aria-label="Sửa tin chờ" rows={3} maxLength={64000} value={draft} disabled={pending}
                  onChange={event => setDraft(event.target.value)}
                  onKeyDown={event => { if (event.key === "Escape" && !pending) { event.preventDefault(); finishEditing(); } }}
                  className="max-h-28 min-h-16 w-full resize-y rounded-lg border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-2 text-[12px] leading-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--nk-accent)]" />
                <div className="mt-1 flex justify-end gap-2 text-[12px]">
                  <button type="button" disabled={pending} onClick={finishEditing} className="min-h-8 rounded-md px-3 hover:bg-[var(--nk-overlay)]">Hủy sửa</button>
                  <button type="button" disabled={pending || !draft.trim()} onClick={() => void run(() => outbox.edit(sessionId, item.id, draft), finishEditing)}
                    className="min-h-8 rounded-md bg-[var(--nk-inverse)] px-3 text-[var(--nk-on-inverse)] disabled:opacity-40">Lưu sửa đổi</button>
                </div>
              </div>}
            </li>;
          })}
        </ol>
      </>}
    </section>
  );
}
