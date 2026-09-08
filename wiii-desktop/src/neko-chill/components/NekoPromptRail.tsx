import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import type { NekoMessage } from "../stores/neko-session-store";

const PROMPT_TITLE_LIMIT = 74;
const PROMPT_PREVIEW_LIMIT = 176;
const WAVE_SEGMENT_COUNT = 44;
const WAVE_MIN_WIDTH = 2;
const WAVE_MAX_WIDTH = 34;
const WAVE_FALLOFF = 0.62;
const WAVE_SMOOTHING_MS = 68;
const SCROLL_WAVE_FRAME_MS = 48;
const RAIL_EDGE_INSET = 0.03;

export interface NekoPromptLandmark {
  id: string;
  messageIndex: number;
  title: string;
  preview: string | null;
  position: number;
}

function compactText(value: string, limit: number): string {
  const compact = value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/[`*_>#\[\]()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (compact.length <= limit) return compact;
  return `${compact.slice(0, Math.max(1, limit - 1)).trimEnd()}…`;
}

function assistantPreview(message: NekoMessage | undefined): string | null {
  if (!message || message.role !== "assistant") return null;
  const answer = message.blocks?.find((block) => block.type === "answer");
  if (answer?.type === "answer") {
    const preview = compactText(answer.content, PROMPT_PREVIEW_LIMIT);
    return preview || null;
  }
  return null;
}

export function buildPromptLandmarks(messages: NekoMessage[]): NekoPromptLandmark[] {
  const denominator = Math.max(1, messages.length - 1);
  const landmarks: NekoPromptLandmark[] = [];
  let waitingForReply: number[] = [];

  messages.forEach((message, messageIndex) => {
    if (message.role === "user" && message.text?.trim()) {
      landmarks.push({
        id: message.id,
        messageIndex,
        title: compactText(message.text, PROMPT_TITLE_LIMIT),
        preview: null,
        // Keep the first/last hit targets and tooltips inside the visible rail.
        position: Math.min(0.97, Math.max(0.03, messageIndex / denominator)),
      });
      waitingForReply.push(landmarks.length - 1);
      return;
    }

    if (message.role !== "assistant" || waitingForReply.length === 0) return;
    const preview = assistantPreview(message);
    waitingForReply.forEach((landmarkIndex) => {
      landmarks[landmarkIndex] = { ...landmarks[landmarkIndex], preview };
    });
    waitingForReply = [];
  });

  return landmarks;
}

/** A compact exponential envelope: the focused prompt is longest and nearby
 * prompts taper away to form the wave seen in the reference interaction. */
export function promptWaveWidth(index: number, focus: number): number {
  const influence = WAVE_FALLOFF ** Math.abs(index - focus);
  return WAVE_MIN_WIDTH + ((WAVE_MAX_WIDTH - WAVE_MIN_WIDTH) * influence);
}

export function promptWavePath(focus: number): string {
  return Array.from({ length: WAVE_SEGMENT_COUNT }, (_, index) =>
    `M 0 ${index + 0.5} H ${promptWaveWidth(index, focus).toFixed(2)}`,
  ).join(" ");
}

export function viewportScrollProgress(
  scrollTop: number,
  scrollHeight: number,
  clientHeight: number,
): number {
  const maxScroll = Math.max(0, scrollHeight - clientHeight);
  if (maxScroll <= 0) return 0;
  return Math.min(1, Math.max(0, scrollTop / maxScroll));
}

export function promptRailPosition(offset: number, maxScroll: number): number {
  const progress = maxScroll > 0
    ? Math.min(1, Math.max(0, offset / maxScroll))
    : 0;
  return RAIL_EDGE_INSET + (progress * (1 - (RAIL_EDGE_INSET * 2)));
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
    } else {
      high = middle - 1;
    }
  }
  return prompts[activeIndex].id;
}

interface NekoPromptRailProps {
  messages: NekoMessage[];
  scrollRef: RefObject<HTMLDivElement>;
  resolveMessageOffset: (messageIndex: number) => number | null;
  onJump: (landmark: NekoPromptLandmark) => void;
}

export const NekoPromptRail = memo(function NekoPromptRail({
  messages,
  scrollRef,
  resolveMessageOffset,
  onJump,
}: NekoPromptRailProps) {
  const landmarks = useMemo(() => buildPromptLandmarks(messages), [messages]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const activeIdRef = useRef<string | null>(landmarks[0]?.id ?? null);
  const landmarkButtonRefs = useRef(new Map<string, HTMLButtonElement>());
  const landmarkPositionsRef = useRef(new Map<string, number>());
  const wavePathRef = useRef<SVGPathElement | null>(null);
  const scrollFocusRef = useRef(0);
  const scrollWavePaintAtRef = useRef(0);
  const hoverFocusRef = useRef<number | null>(null);
  const scrollFrameRef = useRef(0);
  const waveRef = useRef({
    current: 0,
    target: 0,
    frame: 0 as number | 0,
    lastAt: 0,
    painted: Number.NaN,
  });

  const railPositionFor = useCallback(
    (landmark: NekoPromptLandmark) => landmarkPositionsRef.current.get(landmark.id) ?? landmark.position,
    [],
  );

  const setActiveLandmark = useCallback((nextId: string | null) => {
    const previousId = activeIdRef.current;
    if (previousId === nextId) return;

    const update = (id: string | null, active: boolean) => {
      if (!id) return;
      const button = landmarkButtonRefs.current.get(id);
      if (!button) return;
      if (active) button.setAttribute("aria-current", "location");
      else button.removeAttribute("aria-current");
      const marker = button.querySelector<HTMLElement>("[data-testid='neko-prompt-marker']");
      if (marker) marker.dataset.active = active ? "true" : "false";
    };

    update(previousId, false);
    activeIdRef.current = nextId;
    update(nextId, true);
  }, []);

  const paintWave = useCallback((focus: number) => {
    if (Math.abs(waveRef.current.painted - focus) < 0.002) return;
    waveRef.current.painted = focus;
    wavePathRef.current?.setAttribute("d", promptWavePath(focus));
  }, []);

  const moveWaveTo = useCallback((target: number, immediate = false) => {
    const wave = waveRef.current;
    wave.target = Math.min(Math.max(0, target), WAVE_SEGMENT_COUNT - 1);

    const reduceMotion = typeof window !== "undefined"
      && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (immediate || reduceMotion || typeof requestAnimationFrame === "undefined") {
      if (wave.frame) cancelAnimationFrame(wave.frame);
      wave.frame = 0;
      wave.current = wave.target;
      wave.lastAt = 0;
      paintWave(wave.current);
      return;
    }

    if (wave.frame) return;
    const animate = (now: number) => {
      const state = waveRef.current;
      const elapsed = state.lastAt > 0 ? Math.min(64, now - state.lastAt) : 16;
      state.lastAt = now;
      const blend = 1 - Math.exp(-elapsed / WAVE_SMOOTHING_MS);
      state.current += (state.target - state.current) * blend;
      paintWave(state.current);

      if (Math.abs(state.target - state.current) < 0.002) {
        state.current = state.target;
        state.frame = 0;
        state.lastAt = 0;
        paintWave(state.current);
        return;
      }
      state.frame = requestAnimationFrame(animate);
    };
    wave.frame = requestAnimationFrame(animate);
  }, [paintWave]);

  useLayoutEffect(() => {
    const restoredFocus = Math.min(
      Math.max(0, scrollFocusRef.current),
      WAVE_SEGMENT_COUNT - 1,
    );
    scrollFocusRef.current = restoredFocus;
    waveRef.current.current = restoredFocus;
    waveRef.current.target = restoredFocus;
    waveRef.current.painted = Number.NaN;
    moveWaveTo(restoredFocus, true);
  }, [landmarks, moveWaveTo]);

  useEffect(() => () => {
    if (waveRef.current.frame) cancelAnimationFrame(waveRef.current.frame);
    if (scrollFrameRef.current) cancelAnimationFrame(scrollFrameRef.current);
  }, []);

  useEffect(() => {
    const viewport = scrollRef.current;
    if (!viewport || landmarks.length === 0) return;

    let promptOffsets: Array<{ id: string; offset: number }> = [];
    let maxScroll = 0;
    let viewportHeight = 0;
    let measureTimer = 0;

    const syncActiveLandmark = (now = performance.now()) => {
      const progress = maxScroll > 0
        ? Math.min(1, Math.max(0, viewport.scrollTop / maxScroll))
        : 0;
      const waveFocus = progress * (WAVE_SEGMENT_COUNT - 1);
      scrollFocusRef.current = waveFocus;
      const nextActiveId = activePromptIdAtScroll(
        viewport.scrollTop,
        viewportHeight,
        promptOffsets,
      );
      if (nextActiveId) setActiveLandmark(nextActiveId);
      const wavePaintDue = now - scrollWavePaintAtRef.current >= SCROLL_WAVE_FRAME_MS
        || progress === 0
        || progress === 1;
      if (hoverFocusRef.current === null && wavePaintDue) {
        scrollWavePaintAtRef.current = now;
        moveWaveTo(waveFocus, true);
      }
    };

    const scheduleActiveLandmarkSync = () => {
      if (scrollFrameRef.current) return;
      scrollFrameRef.current = requestAnimationFrame((now) => {
        scrollFrameRef.current = 0;
        syncActiveLandmark(now);
      });
    };

    const measurePromptGeometry = () => {
      measureTimer = 0;
      viewportHeight = viewport.clientHeight;
      maxScroll = Math.max(0, viewport.scrollHeight - viewportHeight);
      promptOffsets = landmarks.map((landmark) => {
        const measuredOffset = resolveMessageOffset(landmark.messageIndex);
        const fallbackOffset = landmark.position * maxScroll;
        return {
          id: landmark.id,
          offset: Math.min(maxScroll, Math.max(0, measuredOffset ?? fallbackOffset)),
        };
      });
      const nextPositions = new Map<string, number>();
      promptOffsets.forEach((prompt, index) => {
        const position = maxScroll > 0
          ? promptRailPosition(prompt.offset, maxScroll)
          : landmarks[index].position;
        nextPositions.set(prompt.id, position);
        const button = landmarkButtonRefs.current.get(prompt.id);
        if (button) button.style.top = `${position * 100}%`;
      });
      landmarkPositionsRef.current = nextPositions;
      scheduleActiveLandmarkSync();
    };

    const schedulePromptGeometryMeasure = () => {
      if (measureTimer) window.clearTimeout(measureTimer);
      measureTimer = window.setTimeout(measurePromptGeometry, 96);
    };

    measurePromptGeometry();
    viewport.addEventListener("scroll", scheduleActiveLandmarkSync, { passive: true });
    const resizeObserver = typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(schedulePromptGeometryMeasure);
    resizeObserver?.observe(viewport);
    if (viewport.firstElementChild instanceof HTMLElement) {
      resizeObserver?.observe(viewport.firstElementChild);
    }
    const frame = requestAnimationFrame(measurePromptGeometry);
    return () => {
      cancelAnimationFrame(frame);
      if (measureTimer) window.clearTimeout(measureTimer);
      if (scrollFrameRef.current) {
        cancelAnimationFrame(scrollFrameRef.current);
        scrollFrameRef.current = 0;
      }
      viewport.removeEventListener("scroll", scheduleActiveLandmarkSync);
      resizeObserver?.disconnect();
    };
  }, [landmarks, moveWaveTo, resolveMessageOffset, scrollRef, setActiveLandmark]);

  useEffect(() => {
    if (landmarks.some((landmark) => landmark.id === activeIdRef.current)) return;
    setActiveLandmark(landmarks[0]?.id ?? null);
  }, [landmarks, setActiveLandmark]);

  if (landmarks.length < 2) return null;

  return (
    <nav
      className="group/rail pointer-events-none absolute bottom-6 left-[18px] top-6 z-20 w-12"
      aria-label="Điều hướng các lời nhắn của bạn"
      data-testid="neko-prompt-rail"
    >
      <div
        aria-hidden="true"
        data-testid="neko-wave-track"
        className="pointer-events-auto absolute inset-0 z-0"
        onMouseMove={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          const relativeY = Math.min(bounds.height, Math.max(0, event.clientY - bounds.top));
          const focus = bounds.height > 0
            ? (relativeY / bounds.height) * (WAVE_SEGMENT_COUNT - 1)
            : 0;
          hoverFocusRef.current = focus;
          moveWaveTo(focus);
        }}
        onMouseLeave={() => {
          hoverFocusRef.current = null;
          moveWaveTo(scrollFocusRef.current);
        }}
      >
        <svg
          aria-hidden="true"
          className="absolute inset-y-0 left-0 w-[34px] overflow-visible text-[var(--nk-text-3)] opacity-35 transition-opacity duration-150 group-hover/rail:opacity-[0.68] motion-reduce:transition-none"
          data-testid="neko-wave-path"
          preserveAspectRatio="none"
          viewBox={`0 0 ${WAVE_MAX_WIDTH} ${WAVE_SEGMENT_COUNT}`}
        >
          <path
            ref={wavePathRef}
            d={promptWavePath(waveRef.current.current)}
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      {landmarks.map((landmark) => {
        const active = landmark.id === activeIdRef.current;
        const previewing = landmark.id === previewId;
        return (
          <button
            key={landmark.id}
            ref={(button) => {
              if (button) {
                landmarkButtonRefs.current.set(landmark.id, button);
                button.style.top = `${railPositionFor(landmark) * 100}%`;
              } else {
                landmarkButtonRefs.current.delete(landmark.id);
              }
            }}
            type="button"
            className="group pointer-events-auto absolute left-0 z-10 h-5 w-11 -translate-y-1/2 cursor-pointer outline-none"
            style={{ top: `${landmark.position * 100}%` }}
            aria-label={`Đi tới lời nhắn: ${landmark.title}`}
            aria-current={active ? "location" : undefined}
            onMouseEnter={() => {
              const focus = railPositionFor(landmark) * (WAVE_SEGMENT_COUNT - 1);
              hoverFocusRef.current = focus;
              setPreviewId(landmark.id);
              moveWaveTo(focus);
            }}
            onMouseLeave={() => {
              hoverFocusRef.current = null;
              setPreviewId((current) => current === landmark.id ? null : current);
              moveWaveTo(scrollFocusRef.current);
            }}
            onFocus={() => {
              const focus = railPositionFor(landmark) * (WAVE_SEGMENT_COUNT - 1);
              hoverFocusRef.current = focus;
              setPreviewId(landmark.id);
              moveWaveTo(focus);
            }}
            onBlur={() => {
              hoverFocusRef.current = null;
              setPreviewId((current) => current === landmark.id ? null : current);
              moveWaveTo(scrollFocusRef.current);
            }}
            onClick={() => {
              setActiveLandmark(landmark.id);
              const focus = railPositionFor(landmark) * (WAVE_SEGMENT_COUNT - 1);
              scrollFocusRef.current = focus;
              moveWaveTo(focus);
              onJump(landmark);
            }}
          >
            <span
              aria-hidden="true"
              className="absolute left-0 top-1/2 h-px w-1.5 -translate-y-1/2 rounded-r-full bg-[var(--nk-text-2)] opacity-[0.62] transition-[width,background-color,opacity] duration-150 group-hover:opacity-90 data-[active=true]:w-3 data-[active=true]:bg-[var(--nk-text)] data-[active=true]:opacity-100 data-[preview=true]:w-3 data-[preview=true]:bg-[var(--nk-text)] data-[preview=true]:opacity-100 motion-reduce:transition-none"
              data-active={active ? "true" : "false"}
              data-preview={previewing ? "true" : "false"}
              data-testid="neko-prompt-marker"
            />
            {previewing ? (
              <span
                role="tooltip"
                className="pointer-events-none absolute left-12 top-1/2 w-[min(360px,calc(100vw-112px))] -translate-y-1/2 rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] p-3 text-left shadow-[0_10px_30px_rgba(18,18,16,0.12)]"
              >
                <span className="block text-[12px] font-medium leading-[18px] text-[var(--nk-text)]">
                  {landmark.title}
                </span>
                <span className="mt-1 block text-[11.5px] leading-[18px] text-[var(--nk-text-3)]">
                  {landmark.preview ?? "Chưa có phản hồi hoàn chỉnh cho lời nhắn này."}
                </span>
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
});
