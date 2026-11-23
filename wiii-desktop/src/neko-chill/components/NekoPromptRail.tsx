import { memo, useEffect, useId, useMemo, useRef, useState, type RefObject } from "react";
import { ChevronDown, List } from "lucide-react";
import type { NekoMessage } from "../stores/neko-session-store";
import { retriedMessageIds } from "../transcript-retries";

export interface NekoPromptLandmark {
  id: string;
  messageIndex: number;
  title: string;
}

export function buildPromptLandmarks(messages: NekoMessage[]): NekoPromptLandmark[] {
  const retries = retriedMessageIds(messages);
  return messages.flatMap((message, messageIndex) => {
    if (message.role !== "user" || !message.text?.trim() || retries.has(message.id)) return [];
    const title = message.text.replace(/```[\s\S]*?```/g, " ")
      .replace(/[`*_>#\[\]()]/g, " ").replace(/\s+/g, " ").trim();
    return [{ id: message.id, messageIndex,
      title: title.length > 120 ? `${title.slice(0, 119).trimEnd()}…` : title || "Đoạn mã" }];
  });
}

export function activePromptIdAtScroll(
  scrollTop: number,
  clientHeight: number,
  prompts: ReadonlyArray<{ id: string; offset: number }>,
): string | null {
  if (prompts.length === 0) return null;
  const readingLine = scrollTop + Math.min(96, clientHeight * 0.18);
  let low = 0;
  let high = prompts.length - 1;
  let activeIndex = 0;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    if (prompts[middle].offset <= readingLine + 1) {
      activeIndex = middle;
      low = middle + 1;
    } else high = middle - 1;
  }
  return prompts[activeIndex].id;
}

interface NekoPromptRailProps {
  messages: NekoMessage[];
  scrollRef: RefObject<HTMLDivElement | null>;
  resolveMessageOffset: (messageIndex: number) => number | null;
  onJump: (landmark: NekoPromptLandmark) => void;
}

/** A named, on-demand index instead of unexplained/overlapping timeline marks. */
export const NekoPromptRail = memo(function NekoPromptRail({
  messages, scrollRef, resolveMessageOffset, onJump,
}: NekoPromptRailProps) {
  const landmarks = useMemo(() => buildPromptLandmarks(messages), [messages]);
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [panelHeight, setPanelHeight] = useState(240);
  const navRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const buttonsRef = useRef(new Map<string, HTMLButtonElement>());
  const panelId = useId();
  useEffect(() => setOpen(false), [landmarks[0]?.id]);

  useEffect(() => {
    const viewport = scrollRef.current;
    if (!viewport || landmarks.length < 2) return;
    let offsets: Array<{ id: string; offset: number }> = [];
    let frame = 0;
    const sync = () => {
      frame = 0;
      setActiveId(activePromptIdAtScroll(viewport.scrollTop, viewport.clientHeight, offsets));
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(sync);
    };
    const measure = () => {
      const maxScroll = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
      offsets = landmarks.map((landmark, index) => ({ id: landmark.id,
        offset: Math.min(maxScroll, Math.max(0,
          resolveMessageOffset(landmark.messageIndex) ?? (index / (landmarks.length - 1)) * maxScroll)),
      }));
      if (viewport.clientHeight > 0) setPanelHeight(Math.min(320, Math.max(40, viewport.clientHeight - 8)));
      schedule();
    };
    measure();
    viewport.addEventListener("scroll", schedule, { passive: true });
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(viewport);
    if (viewport.firstElementChild) observer?.observe(viewport.firstElementChild);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      viewport.removeEventListener("scroll", schedule);
      observer?.disconnect();
    };
  }, [landmarks, resolveMessageOffset, scrollRef]);

  useEffect(() => {
    if (!open) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus({ preventScroll: true });
    };
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !navRef.current?.contains(event.target)) setOpen(false);
    };
    window.addEventListener("keydown", dismiss, true);
    document.addEventListener("pointerdown", outside, true);
    return () => {
      window.removeEventListener("keydown", dismiss, true);
      document.removeEventListener("pointerdown", outside, true);
    };
  }, [open]);

  if (landmarks.length < 2) return null;

  return (
    <nav ref={navRef} className="relative z-20 flex shrink-0 justify-end px-5 py-1"
      aria-label="Điều hướng các lời nhắn của bạn" data-testid="neko-prompt-rail"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}>
      <button ref={triggerRef} type="button" aria-expanded={open} aria-controls={panelId}
        className="flex h-7 items-center gap-1.5 rounded-md px-2 text-[11px] text-[var(--nk-text-3)] hover:bg-[var(--nk-overlay)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-text-3)]"
        onClick={() => setOpen(current => !current)}
        onKeyDown={(event) => {
          if (event.key !== "ArrowDown") return;
          event.preventDefault();
          setOpen(true);
          const selected = landmarks.find(landmark => landmark.id === activeId) ?? landmarks[0];
          requestAnimationFrame(() => buttonsRef.current.get(selected.id)?.focus());
        }}>
        <List aria-hidden="true" className="h-3.5 w-3.5" />
        Câu hỏi <span className="tabular-nums">{landmarks.length}</span>
        <ChevronDown aria-hidden="true" className={`h-3 w-3 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div id={panelId} className="nk-scroll-surface absolute right-5 top-full w-[min(360px,calc(100%_-_2.5rem))] overflow-y-auto rounded-xl border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] p-1.5 shadow-lg"
          style={{ maxHeight: panelHeight }}>
          <ol className="space-y-1">
            {landmarks.map((landmark, index) => (
              <li key={landmark.id}>
                <button ref={(button) => {
                  if (button) buttonsRef.current.set(landmark.id, button);
                  else buttonsRef.current.delete(landmark.id);
                }} type="button" aria-label={`Đi tới lời nhắn ${index + 1}: ${landmark.title}`}
                  aria-current={activeId === landmark.id ? "location" : undefined}
                  className="flex min-h-9 w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-[11.5px] leading-[18px] text-[var(--nk-text-2)] hover:bg-[var(--nk-overlay)] focus-visible:bg-[var(--nk-overlay)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--nk-text-3)] aria-[current=location]:bg-[var(--nk-inset)]"
                  onKeyDown={(event) => {
                    const next = event.key === "ArrowDown" ? Math.min(index + 1, landmarks.length - 1)
                      : event.key === "ArrowUp" ? Math.max(index - 1, 0)
                        : event.key === "Home" ? 0 : event.key === "End" ? landmarks.length - 1 : null;
                    if (next === null) return;
                    event.preventDefault();
                    buttonsRef.current.get(landmarks[next].id)?.focus();
                  }}
                  onClick={() => {
                    setOpen(false);
                    onJump(landmark);
                  }}>
                  <span aria-hidden="true" className="min-w-5 shrink-0 text-right tabular-nums text-[var(--nk-ghost)]">{index + 1}</span>
                  <span className="min-w-0 break-words">{landmark.title}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </nav>
  );
});
