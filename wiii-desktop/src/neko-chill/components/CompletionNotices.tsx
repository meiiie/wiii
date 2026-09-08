import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { completionPlayer } from "../completion-sound";
import { useCompletionNoticeStore, type CompletionNotice } from "../stores/completion-notice-store";

function Notice({ notice, onOpen }: { notice: CompletionNotice; onOpen: (sessionId: string) => void }) {
  const dismiss = useCompletionNoticeStore((state) => state.dismiss);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    if (hovered || focused) return;
    const timer = setTimeout(() => dismiss(notice.id), 7000);
    return () => clearTimeout(timer);
  }, [dismiss, notice.id, hovered, focused]);
  return <article className="nk-completion-notice pointer-events-auto rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-3 shadow-lg"
    onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
    onFocus={() => setFocused(true)} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false);
    }}>
    <div className="flex items-start gap-2.5">
      <Check aria-hidden="true" size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1 text-[12px] leading-5">
        <p className="font-medium">Đã trả lời xong</p>
        <p className="truncate text-[var(--nk-text-2)]">{notice.title}</p>
        <button type="button" className="mt-1 font-medium underline underline-offset-4"
          onClick={() => { onOpen(notice.sessionId); dismiss(notice.id); }}>Xem kết quả</button>
      </div>
      <button type="button" aria-label="Đóng thông báo hoàn tất" className="nk-chrome-button grid h-7 w-7 shrink-0 place-items-center rounded"
        onClick={() => dismiss(notice.id)}><X aria-hidden="true" size={15} /></button>
    </div>
  </article>;
}

export function CompletionNotices({ onOpen }: { onOpen: (sessionId: string) => void }) {
  const { notices, enabled, sound } = useCompletionNoticeStore(useShallow((state) => ({
    notices: state.notices, enabled: state.enabled, sound: state.sound,
  })));
  useEffect(() => {
    if (!enabled || !sound) return;
    let disposed = false;
    const removeListeners = () => {
      window.removeEventListener("pointerdown", unlock, true);
      window.removeEventListener("keydown", unlock, true);
    };
    const unlock = () => { void completionPlayer.prepare().then((ready) => {
      if (ready && !disposed) removeListeners();
    }); };
    window.addEventListener("pointerdown", unlock, true);
    window.addEventListener("keydown", unlock, true);
    return () => { disposed = true; removeListeners(); };
  }, [enabled, sound]);
  useEffect(() => () => completionPlayer.dispose(), []);
  return <section aria-label="Thông báo hoàn tất" aria-live="polite" aria-relevant="additions"
    className="pointer-events-none fixed bottom-4 left-4 z-[60] flex w-[320px] max-w-[calc(100vw-32px)] flex-col gap-2 text-[var(--nk-text)]">
    {notices.map((notice) => <Notice key={notice.id} notice={notice} onOpen={onOpen} />)}
  </section>;
}
