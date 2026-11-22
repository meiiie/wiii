/**
 * Neko Chill transcript — workspace-shell styling (#904): 780px
 * centered column, quiet thinking rail, dot-status tool rows, shared
 * MarkdownRenderer for answers, with measured row virtualization for long sessions.
 */
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, BookOpen, ChevronRight, Command, FolderGit2 } from "lucide-react";
import { NEKO_STARTER_PROMPTS } from "../starter-prompts";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { NekoActivityIcon, resolveNekoToolIconKind } from "@/components/icons/neko";
import type {
  ContentBlock,
  ThinkingBlockData,
  ToolExecutionBlockData,
} from "@/api/types/content-blocks";
import type { NekoSession } from "../stores/neko-session-store";
import { getSessionControlNotices, getStoppedPrompt, workspaceIsolationLabel, type SessionControlNotice } from "../session-control-status";
import { PermissionCard } from "./PermissionCard";
import { NekoPromptRail, type NekoPromptLandmark } from "./NekoPromptRail";
import { nativeSessionNeedsRecovery } from "../stores/session-native-recovery";
import { captureTranscriptReadingAnchor, restoreTranscriptReadingAnchor, captureTranscriptReadingBookmark, restoreTranscriptReadingBookmark, type TranscriptReadingPosition } from "../transcript-reading-anchor";

export const NEKO_TRANSCRIPT_VIRTUALIZATION_THRESHOLD = 50;

export function shouldVirtualizeTranscript(messageCount: number): boolean {
  return messageCount > NEKO_TRANSCRIPT_VIRTUALIZATION_THRESHOLD;
}

export function dispatchedKnowledgeContexts(session: NekoSession) {
  const dispatched = new Set(
    session.events.flatMap((event) =>
      event.data.type === "dispatch-invoked" && event.data.action === "knowledge"
        ? [event.data.targetEventId]
        : [],
    ),
  );
  return session.events.flatMap((event) =>
    event.eventId &&
    event.data.type === "knowledge-context" &&
    dispatched.has(event.eventId)
      ? [event.data]
      : [],
  );
}

export function formatReasoningDuration(block: ThinkingBlockData): string | null {
  if (
    block.startTime === undefined
    || block.endTime === undefined
    || block.endTime < block.startTime
  ) {
    return null;
  }
  const seconds = Math.max(1, Math.round((block.endTime - block.startTime) / 1_000));
  if (seconds < 60) return `${seconds} giây`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder > 0 ? `${minutes} phút ${remainder} giây` : `${minutes} phút`;
}

export function formatToolActivity(title: string, detail?: string, maxLength = 120) {
  const compactTitle = title.replace(/\s+/g, " ").trim();
  const match = compactTitle.match(/^([^\s(]+)(?:\s+|\((.*)\)$)?/);
  const label = match?.[1] || compactTitle || "Tool";
  const titleDetail = match?.[2] ?? compactTitle.slice(label.length).trim();
  const compactDetail = (detail || titleDetail).replace(/\s+/g, " ").trim();
  const preview = compactDetail.length > maxLength
    ? `${compactDetail.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…`
    : compactDetail;
  return { label, preview };
}

type ActivityBlock = ThinkingBlockData | ToolExecutionBlockData;
type TranscriptBlockGroup =
  | { kind: "activity"; blocks: ActivityBlock[] }
  | { kind: "content"; block: ContentBlock };

function isActivityBlock(block: ContentBlock): block is ActivityBlock {
  return block.type === "thinking" || block.type === "tool_execution";
}

export function groupTranscriptBlocks(blocks: ContentBlock[]): TranscriptBlockGroup[] {
  const groups: TranscriptBlockGroup[] = [];
  let activity: ActivityBlock[] = [];
  const flushActivity = () => {
    if (activity.length === 0) return;
    groups.push({ kind: "activity", blocks: activity });
    activity = [];
  };

  for (const block of blocks) {
    if (isActivityBlock(block)) {
      activity.push(block);
      continue;
    }
    flushActivity();
    groups.push({ kind: "content", block });
  }
  flushActivity();
  return groups;
}

export function toolActivityFailed(block: ToolExecutionBlockData): boolean {
  return block.outcome === "failed" || block.outcome === "cancelled";
}

export function ThinkingDisclosure({
  block,
  active = false,
}: {
  block: ThinkingBlockData;
  active?: boolean;
}) {
  // Provider thought text/metadata is optional detail, not Vietnamese UI copy.
  const label = active ? "Đang suy nghĩ" : "Đã suy nghĩ";
  const duration = formatReasoningDuration(block);

  return (
    <details
      className="group my-0.5 min-w-0 max-w-full text-[12px] text-[var(--nk-text-3)]"
      data-testid="thinking-block"
    >
      <summary
        className="flex min-h-6 w-full min-w-0 cursor-pointer list-none items-center gap-2 overflow-hidden rounded-md px-1 outline-none transition-colors hover:bg-[var(--nk-inset)] focus-visible:ring-2 focus-visible:ring-[var(--nk-text-3)] [&::-webkit-details-marker]:hidden"
        aria-label={`${label}. Mở chi tiết suy luận`}
      >
        <NekoActivityIcon
          kind="reasoning"
          className={
            active
              ? "h-3.5 w-3.5 shrink-0 text-[var(--nk-accent)] nk-status-pulse"
              : "h-3.5 w-3.5 shrink-0 text-[var(--nk-ghost)]"
          }
        />
        <span className="shrink-0 font-medium text-[var(--nk-text-2)]">{label}</span>
        <span className="min-w-0 flex-1" />
        {duration ? <span className="ml-auto shrink-0 tabular-nums">{duration}</span> : null}
        <ChevronRight
          aria-hidden="true"
          className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
        />
      </summary>
      <div className="ml-[7px] max-h-56 overflow-y-auto border-l border-[var(--nk-border)] py-1 pl-4 pr-2 text-[12px] leading-[18px] text-[var(--nk-text-3)]">
        <MarkdownRenderer content={block.content} streaming={active} />
      </div>
    </details>
  );
}

export function ToolDisclosure({ block }: { block: ToolExecutionBlockData }) {
  const { label, preview } = formatToolActivity(block.tool.name, block.tool.result);
  const running = block.status === "pending";
  const failed = toolActivityFailed(block);
  return (
    <details
      className="group my-0.5 min-w-0 max-w-full text-[12px] text-[var(--nk-text-3)]"
      data-testid="tool-strip"
    >
      <summary
        className="flex min-h-6 w-full min-w-0 cursor-pointer list-none items-center gap-2 overflow-hidden rounded-md px-1 v3-outline-none transition-colors hover:bg-[var(--nk-inset)] focus-visible:ring-2 focus-visible:ring-[var(--nk-focus)] [&::-webkit-details-marker]:hidden"
        aria-label={`${label} ${running ? "đang chạy" : failed ? "thất bại" : "hoàn tất"}. Mở chi tiết`}
      >
        <NekoActivityIcon
          kind={resolveNekoToolIconKind(label)}
          className={
            running
              ? "h-3.5 w-3.5 shrink-0 nk-status-pulse text-[var(--nk-warning)]"
              : failed
                ? "h-3.5 w-3.5 shrink-0 text-[var(--nk-danger)]"
                : "h-3.5 w-3.5 shrink-0 text-[var(--nk-success)]"
          }
        />
        <span className="shrink-0 font-medium text-[var(--nk-text-2)]">{label}</span>
        {preview ? <span className="min-w-0 flex-1 truncate text-[var(--nk-text-3)]">— {preview}</span> : null}
        <span className="ml-auto shrink-0 text-[10.5px]">{running ? "Đang chạy" : failed ? "Chưa hoàn tất" : "Xong"}</span>
        <ChevronRight
          aria-hidden="true"
          className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
        />
      </summary>
      <div className="ml-[7px] max-h-56 overflow-y-auto border-l border-[var(--nk-border)] py-1 pl-4 pr-2 text-[11.5px] leading-[18px]">
        <p className="wrap-break-word font-mono text-[var(--nk-text-2)]">{block.tool.name}</p>
        {block.tool.result ? (
          <p className="mt-1 whitespace-pre-wrap wrap-break-word text-[var(--nk-text-3)]">{block.tool.result}</p>
        ) : null}
      </div>
    </details>
  );
}

function ActivityGroup({
  blocks,
  activeBlock,
}: {
  blocks: ActivityBlock[];
  activeBlock?: ContentBlock;
}) {
  if (blocks.length === 1) {
    const block = blocks[0];
    return block ? <Block block={block} active={block === activeBlock} /> : null;
  }

  const thinkingCount = blocks.filter((block) => block.type === "thinking").length;
  const toolCount = blocks.length - thinkingCount;
  const failureCount = blocks.filter(
    (block) => block.type === "tool_execution" && toolActivityFailed(block),
  ).length;
  const running = blocks.some(
    (block) => block === activeBlock || (block.type === "tool_execution" && block.status === "pending"),
  );
  const parts = [
    thinkingCount > 0 ? `${thinkingCount} phân tích` : null,
    toolCount > 0 ? `${toolCount} công cụ` : null,
    failureCount > 0 ? `${failureCount} lỗi` : null,
  ].filter((part): part is string => part !== null);
  const summary = parts.join(" · ");
  const title = failureCount > 0
    ? `${failureCount} bước cần xem lại`
    : running
      ? "Đang thực hiện"
      : `${blocks.length} bước đã thực hiện`;

  return (
    <details
      className="group my-0.5 min-w-0 max-w-full text-[12px] text-[var(--nk-text-3)]"
      data-testid="activity-group"
    >
      <summary
        className="flex min-h-6 w-full min-w-0 cursor-pointer list-none items-center gap-2 overflow-hidden rounded-md px-1 v3-outline-none transition-colors hover:bg-[var(--nk-inset)] focus-visible:ring-2 focus-visible:ring-[var(--nk-focus)] [&::-webkit-details-marker]:hidden"
        aria-label={`${title}, ${summary}. Mở chi tiết`}
      >
        <NekoActivityIcon
          kind={failureCount > 0 ? "warning" : "activity"}
          className={
            failureCount > 0
              ? "h-3.5 w-3.5 shrink-0 text-[var(--nk-danger)]"
              : running
                ? "h-3.5 w-3.5 shrink-0 nk-status-pulse text-[var(--nk-accent)]"
                : "h-3.5 w-3.5 shrink-0 text-[var(--nk-ghost)]"
          }
        />
        <span className="shrink-0 font-medium text-[var(--nk-text-2)]">{title}</span>
        <span className="sr-only">{summary}</span>
        <span className="min-w-0 flex-1" />
        <ChevronRight
          aria-hidden="true"
          className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
        />
      </summary>
      <div className="ml-[7px] border-l border-[var(--nk-border)] py-0.5 pl-3">
        {blocks.map((block) => (
          <Block key={block.id} block={block} active={block === activeBlock} />
        ))}
      </div>
    </details>
  );
}

function Block({ block, active = false }: { block: ContentBlock; active?: boolean }) {
  switch (block.type) {
    case "thinking":
      return <ThinkingDisclosure block={block} active={active} />;
    case "tool_execution":
      return <ToolDisclosure block={block} />;
    case "answer":
      return <MarkdownRenderer content={block.content} streaming={active} className="my-2 min-w-0 text-[13.5px] [overflow-wrap:anywhere]" />;
    default:
      // Cloud-only block kinds never arrive from local drivers in v0.
      return null;
  }
}

const MessageRow = memo(function MessageRow({
  message,
  messageIndex,
  streaming = false,
  onReady,
}: {
  message: NekoSession["messages"][number];
  messageIndex: number;
  streaming?: boolean;
  onReady?: (node: HTMLDivElement | null) => void;
}) {
  const blocks = message.blocks ?? [];
  const lastBlock = blocks[blocks.length - 1];
  const groups = groupTranscriptBlocks(blocks);
  return message.role === "user" ? (
    <div
      ref={onReady}
      tabIndex={-1}
      className="my-3 flex scroll-mt-6 justify-end rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
      data-neko-message-id={message.id}
      data-neko-message-index={messageIndex}
    >
      <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl bg-[var(--nk-raised)] px-3.5 py-2 text-[13.5px] leading-[20px] text-[var(--nk-text)]">
        {message.text}
      </div>
    </div>
  ) : (
    <div
      className="my-3 min-w-0 max-w-full scroll-mt-6 overflow-hidden"
      data-neko-message-id={message.id}
      data-neko-message-index={messageIndex}
    >
      {groups.map((group) => group.kind === "activity" ? (
        <ActivityGroup
          key={`activity-${group.blocks[0]?.id ?? "empty"}`}
          blocks={group.blocks}
          activeBlock={streaming ? lastBlock : undefined}
        />
      ) : (
        <Block key={group.block.id} block={group.block} active={streaming && group.block === lastBlock} />
      ))}
    </div>
  );
});

export function streamingActivityLabel(session: NekoSession): string {
  const assistant = [...session.messages].reverse().find((message) => message.role === "assistant");
  const blocks = assistant?.blocks ?? [];
  const pendingTool = [...blocks]
    .reverse()
    .find((block) => block.type === "tool_execution" && block.status === "pending");
  if (pendingTool?.type === "tool_execution") {
    return `Đang chạy ${formatToolActivity(pendingTool.tool.name).label}…`;
  }
  const last = blocks[blocks.length - 1];
  if (last?.type === "thinking" && last.endTime === undefined) {
    return `${session.agentName} đang suy nghĩ…`;
  }
  return `${session.agentName} đang viết…`;
}

function RetryStoppedTurn({ onRetry }: { onRetry: () => Promise<void> }) {
  const pending = useRef(false);
  const [state, setState] = useState<"idle" | "pending" | "failed">("idle");
  const retry = async () => {
    if (pending.current) return;
    pending.current = true;
    setState("pending");
    try {
      await onRetry();
      setState("idle");
    } catch {
      setState("failed");
    } finally {
      pending.current = false;
    }
  };
  return <div>
    <button type="button" className="nk-chrome-button rounded-md border border-[var(--nk-border)] px-2 py-0.5 text-[var(--nk-text)] disabled:opacity-50"
      aria-label="Thử lại tin nhắn vừa dừng" disabled={state === "pending"} aria-busy={state === "pending"}
      onClick={() => void retry()}>
      {state === "pending" ? "Đang gửi lại…" : "Thử lại"}
    </button>
    {state === "failed" ? <p role="alert">Chưa gửi lại được. Hãy thử lại.</p> : null}
  </div>;
}

export function SessionControlStatus({
  session,
  notices = getSessionControlNotices(session),
  onRecover,
  onRetry,
}: { session: NekoSession; notices?: SessionControlNotice[]; onRecover?: () => void; onRetry?: (eventId: string) => Promise<void> }) {
  const stoppedPrompt = onRetry ? getStoppedPrompt(session) : null;
  if (onRecover && nativeSessionNeedsRecovery(session)) {
    return <div role="status" aria-live="polite" className="my-2 rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 py-3 text-[12px] leading-5">
      <p>{session.closePending ? "Đang dừng phiên cũ…" : session.nativeRecoveryRequired ? session.statusDetail : "Cuộc trò chuyện cần nối lại."}</p>
      <p className="mt-1 text-[var(--nk-text-3)]">Lịch sử và bản nháp được giữ lại.</p>
      <button type="button" className="nk-chrome-button mt-2 rounded-md border border-[var(--nk-border)] px-3 py-1.5 disabled:opacity-50"
        data-testid="neko-recover-session" disabled={session.closePending || session.deletePending}
        aria-busy={session.closePending} onClick={onRecover}>
        {session.closePending ? "Đang nối lại…" : "Dừng phiên cũ và tiếp tục"}
      </button>
    </div>;
  }
  return notices.map((notice) => (
    <div
      key={notice.kind}
      role={notice.tone === "danger" ? "alert" : session.pendingPermission ? "note" : "status"}
      aria-live={notice.tone === "danger" ? "assertive" : "polite"}
      aria-atomic="true"
      data-testid={`session-control-${notice.kind}`}
      data-stage={notice.stage}
      className={`my-2 min-w-0 max-w-full text-[12px] leading-5 [overflow-wrap:anywhere] ${notice.tone === "quiet" ? "flex items-start gap-2 px-1 text-[var(--nk-text-3)]" : `rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 py-2 ${notice.tone === "danger" ? "text-[var(--nk-danger)]" : "text-[var(--nk-warning)]"}`}`}
    >
      {notice.tone === "quiet" ? <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[var(--nk-ghost)]" /> : null}
      <p className="whitespace-pre-wrap">{notice.text}</p>
      {notice.kind === "cancel" && stoppedPrompt && onRetry ? (
        <RetryStoppedTurn key={`${session.id}:${stoppedPrompt.eventId}`} onRetry={() => onRetry(stoppedPrompt.eventId)} />
      ) : null}
      {notice.guidance ? <p className="mt-1 text-[var(--nk-text-3)]">{notice.guidance}</p> : null}
    </div>
  ));
}

interface NekoTranscriptProps {
  session: NekoSession;
  onResolvePermission: (optionId: string | null) => void;
  onInsertPrompt: (text: string) => void;
  onRecover?: () => void;
  onRetry?: (eventId: string) => Promise<void>;
  readingPositions?: Map<string, TranscriptReadingPosition>;
}

export function NekoTranscript({
  session,
  onResolvePermission,
  onInsertPrompt,
  onRecover,
  onRetry,
  readingPositions,
}: NekoTranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const followFrameRef = useRef<number | null>(null);
  const automaticScrollTopRef = useRef<number | null>(null);
  const pendingPromptFocusRef = useRef<{ sessionId: string; messageId: string } | null>(null);
  const messagesRef = useRef(session.messages);
  messagesRef.current = session.messages;
  const [followingTail, setFollowingTail] = useState(() => readingPositions?.get(session.id)?.followingTail ?? true);
  const followingTailRef = useRef(followingTail);
  const pendingReadingBookmarkRef = useRef<TranscriptReadingPosition["bookmark"]>(null);
  const restoredReadingTopRef = useRef<number | null>(null);
  const messageCount = session.messages.length;
  const lastMessage = session.messages[messageCount - 1];
  const previousLastMessageRef = useRef(lastMessage?.id);
  const lastBlockCount = lastMessage?.blocks?.length ?? 0;
  const useVirtual = shouldVirtualizeTranscript(messageCount);
  const promptRailMessages = useMemo(
    () => session.messages,
    [messageCount, session.id, session.status === "streaming"],
  );
  const knowledgeContexts = useMemo(
    () => dispatchedKnowledgeContexts(session),
    [session.events],
  );
  const controlNotices = useMemo(
    () => getSessionControlNotices(session),
    [session.cancelPending, session.events, session.runtime, session.status, session.statusDetail],
  );
  const virtualizer = useVirtualizer({
    count: messageCount,
    getScrollElement: () => scrollRef.current,
    estimateSize: useCallback(
      (index: number) => (messagesRef.current[index]?.role === "user" ? 64 : 180),
      [],
    ),
    overscan: 4,
    gap: 4,
    enabled: useVirtual,
    initialOffset: readingPositions?.get(session.id)?.scrollTop ?? 0,
  });

  const measureVirtualRow = useCallback((node: HTMLDivElement | null) => {
    virtualizer.measureElement(node);
    if (!node) return;
    return () => {
      const ownedFocus = node.contains(document.activeElement);
      // Ref cleanup also runs during StrictMode replay, without a DOM removal.
      // Wait for the commit, then recover only a truly removed focus owner.
      queueMicrotask(() => {
        if (ownedFocus && !node.isConnected && document.activeElement === document.body) {
          scrollRef.current?.focus({ preventScroll: true });
        }
        virtualizer.measureElement(null);
      });
    };
  }, [virtualizer]);

  const updateFollowingTail = useCallback((next: boolean) => {
    if (next) pendingReadingBookmarkRef.current = null;
    if (followingTailRef.current === next) return;
    followingTailRef.current = next;
    setFollowingTail(next);
    const saved = readingPositions?.get(session.id);
    if (saved) readingPositions?.set(session.id, { ...saved, followingTail: next });
  }, [readingPositions, session.id]);

  const restorePendingReadingPosition = useCallback(() => {
    const viewport = scrollRef.current;
    const bookmark = pendingReadingBookmarkRef.current;
    if (!viewport || !bookmark || !restoreTranscriptReadingBookmark(viewport, bookmark)) return false;
    pendingReadingBookmarkRef.current = null;
    restoredReadingTopRef.current = viewport.scrollTop;
    return true;
  }, []);

  const scrollToLatest = useCallback(
    (behavior: ScrollBehavior = "auto") => {
      pendingPromptFocusRef.current = null;
      if (useVirtual && messageCount > 0) {
        virtualizer.scrollToIndex(messageCount - 1, { align: "end", behavior });
      } else if (typeof bottomRef.current?.scrollIntoView === "function") {
        bottomRef.current.scrollIntoView({ block: "end", behavior });
      }
      automaticScrollTopRef.current = behavior === "auto" ? scrollRef.current?.scrollTop ?? null : null;
    },
    [messageCount, useVirtual, virtualizer],
  );

  const focusPromptTarget = useCallback((node: HTMLDivElement | null) => {
    const pending = pendingPromptFocusRef.current;
    if (!node || pending?.sessionId !== session.id || pending.messageId !== node.dataset.nekoMessageId) return;
    pendingPromptFocusRef.current = null;
    node.focus({ preventScroll: true });
  }, [session.id]);

  const jumpToPrompt = useCallback(
    (landmark: NekoPromptLandmark) => {
      const reducedMotion = typeof window.matchMedia === "function"
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const behavior: ScrollBehavior = reducedMotion ? "auto" : "smooth";
      updateFollowingTail(false);
      pendingPromptFocusRef.current = { sessionId: session.id, messageId: landmark.id };
      if (useVirtual) {
        virtualizer.scrollToIndex(landmark.messageIndex, { align: "start", behavior });
      }
      const target = scrollRef.current?.querySelector<HTMLDivElement>(
        `[data-neko-message-index="${landmark.messageIndex}"]`,
      );
      if (!useVirtual) target?.scrollIntoView({ block: "start", behavior });
      // Offscreen virtual rows receive focus from onReady when they mount.
      if (target) focusPromptTarget(target);
      else if (!useVirtual) {
        pendingPromptFocusRef.current = null;
        scrollRef.current?.focus({ preventScroll: true });
      }
    },
    [focusPromptTarget, session.id, updateFollowingTail, useVirtual, virtualizer],
  );

  const resolveMessageOffset = useCallback((messageIndex: number): number | null => {
    const viewport = scrollRef.current;
    if (!viewport) return null;
    if (useVirtual) {
      return virtualizer.getOffsetForIndex(messageIndex, "start")?.[0] ?? null;
    }
    const target = viewport.querySelector<HTMLElement>(
      `[data-neko-message-index="${messageIndex}"]`,
    );
    if (!target) return null;
    const viewportBounds = viewport.getBoundingClientRect();
    const targetBounds = target.getBoundingClientRect();
    return viewport.scrollTop + targetBounds.top - viewportBounds.top;
  }, [useVirtual, virtualizer]);

  useLayoutEffect(() => {
    pendingPromptFocusRef.current = null;
    automaticScrollTopRef.current = null;
    const saved = readingPositions?.get(session.id);
    updateFollowingTail(saved?.followingTail ?? true);
    pendingReadingBookmarkRef.current = saved?.followingTail === false ? saved.bookmark : null;
    if (saved && !saved.followingTail && scrollRef.current) {
      scrollRef.current.scrollTop = saved.scrollTop;
      if (useVirtual && saved.bookmark) {
        const index = messagesRef.current.findIndex(({ id }) => id === saved.bookmark?.messageId);
        if (index >= 0) virtualizer.scrollToIndex(index, { align: "start" });
      }
      restorePendingReadingPosition();
      restoredReadingTopRef.current = scrollRef.current.scrollTop;
    }
    previousLastMessageRef.current = messagesRef.current[messagesRef.current.length - 1]?.id;
  }, [session.id, readingPositions, restorePendingReadingPosition, updateFollowingTail, useVirtual, virtualizer]);

  // Virtual rows and delayed Markdown can mount after the initial restoration.
  useLayoutEffect(() => { restorePendingReadingPosition(); });

  useEffect(() => {
    const changed = previousLastMessageRef.current !== lastMessage?.id;
    previousLastMessageRef.current = lastMessage?.id;
    if (changed && lastMessage?.role === "user") updateFollowingTail(true);
  }, [lastMessage?.id, lastMessage?.role, updateFollowingTail]);

  const scheduleFollow = useCallback(() => {
    if (!followingTailRef.current || followFrameRef.current !== null) return;
    followFrameRef.current = requestAnimationFrame(() => {
      followFrameRef.current = null;
      // A scroll or prompt-rail action since scheduling owns the reading position.
      if (followingTailRef.current) scrollToLatest();
    });
  }, [scrollToLatest]);

  useEffect(() => {
    const viewport = scrollRef.current;
    const content = contentRef.current;
    if (!viewport || !content) return;
    let width = viewport.clientWidth;
    let anchor: ReturnType<typeof captureTranscriptReadingAnchor> = null;
    let restoredScrollTop: number | null = null;
    const rememberReadingPosition = () => {
      if (pendingReadingBookmarkRef.current) return;
      if (followingTailRef.current) anchor = null;
      // A reflow can emit scroll before ResizeObserver. Keep the pre-resize
      // text position until it has been restored, rather than caching the jump.
      else if (width === viewport.clientWidth) anchor = captureTranscriptReadingAnchor(viewport);
      if (width === viewport.clientWidth) readingPositions?.set(session.id, {
        followingTail: followingTailRef.current,
        scrollTop: viewport.scrollTop,
        bookmark: followingTailRef.current ? null : captureTranscriptReadingBookmark(viewport, anchor),
      });
    };
    const onScroll = () => {
      // Reflow may clamp scrollTop to the new bottom. That is not the reader
      // choosing to resume tail-following; restore their text position first.
      if (width !== viewport.clientWidth) return;
      if (restoredReadingTopRef.current !== null && Math.abs(viewport.scrollTop - restoredReadingTopRef.current) < 1) return;
      if (restoredScrollTop !== null && Math.abs(viewport.scrollTop - restoredScrollTop) < 1) return;
      // A requested follow can emit scroll after another streaming chunk has
      // grown the content. That old position is not the reader scrolling away.
      if (followingTailRef.current && automaticScrollTopRef.current !== null
        && Math.abs(viewport.scrollTop - automaticScrollTopRef.current) < 1) return;
      restoredScrollTop = null;
      restoredReadingTopRef.current = null;
      pendingReadingBookmarkRef.current = null;
      updateFollowingTail(viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 96);
      rememberReadingPosition();
    };
    const onResize = () => {
      if (restorePendingReadingPosition()) anchor = captureTranscriptReadingAnchor(viewport);
      const restored = !followingTailRef.current && restoreTranscriptReadingAnchor(viewport, anchor);
      width = viewport.clientWidth;
      // Keep the same character across every frame of an animated resize.
      // Only an actual reading scroll should choose a different text anchor.
      if (restored) restoredScrollTop = viewport.scrollTop;
      else rememberReadingPosition();
      scheduleFollow();
    };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(onResize);
    viewport.addEventListener("scroll", onScroll, { passive: true });
    if (viewport) observer?.observe(viewport);
    if (content) observer?.observe(content);
    scheduleFollow();
    return () => {
      observer?.disconnect();
      viewport.removeEventListener("scroll", onScroll);
      if (followFrameRef.current !== null) cancelAnimationFrame(followFrameRef.current);
      followFrameRef.current = null;
    };
  }, [session.id, scheduleFollow, updateFollowingTail, readingPositions, restorePendingReadingPosition]);

  // Message updates also cover environments without ResizeObserver. The observer
  // covers delayed Markdown/image layout and composer-induced viewport changes.
  useEffect(scheduleFollow, [lastMessage, lastBlockCount, session.pendingPermission, scheduleFollow]);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <NekoPromptRail
        messages={promptRailMessages}
        scrollRef={scrollRef}
        resolveMessageOffset={resolveMessageOffset}
        onJump={jumpToPrompt}
      />
      <div
        ref={scrollRef}
        className="nk-scroll-surface min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto focus-visible:v3-outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--nk-focus-soft)]"
        tabIndex={0}
        data-testid="neko-transcript"
        role="log"
        aria-label="Lịch sử phiên Neko Chill"
        aria-live={session.status === "streaming" ? "off" : "polite"}
      >
      <div ref={contentRef} className="mx-auto min-w-0 w-full max-w-[780px] overflow-hidden px-5 py-4 min-[900px]:px-6">
        {session.messages.length === 0 && session.status === "idle" ? (
          <section className="mx-auto flex max-w-[560px] flex-col items-center px-4 py-[10vh] text-center" aria-label="Bắt đầu phiên">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--nk-inset)] text-[var(--nk-text-2)]">
              <FolderGit2 aria-hidden="true" className="h-[18px] w-[18px]" />
            </span>
            <h2 className="mt-4 text-[18px] font-medium tracking-[-0.02em] text-[var(--nk-text)]">
              Sẵn sàng trong {session.workspace?.name ?? "dự án này"}
            </h2>
            <p className="mt-1.5 max-w-[460px] text-[12.5px] leading-5 text-[var(--nk-text-3)]">
              Thư mục đã chọn là ngữ cảnh của phiên. Hãy mô tả kết quả bạn muốn;
              các gợi ý dưới đây chỉ được chèn vào ô soạn để bạn xem lại.
            </p>
            <p className="mt-2 max-w-[460px] text-[11px] leading-4 text-[var(--nk-ghost)] [overflow-wrap:anywhere]" data-testid="workspace-isolation-notice">
              {workspaceIsolationLabel(session)}
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {NEKO_STARTER_PROMPTS.map((starter) => (
                <button
                  key={starter.label}
                  type="button"
                  aria-label={`Chèn gợi ý ${starter.label}`}
                  className="rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 py-2 text-[12px] text-[var(--nk-text-2)] transition-colors hover:border-[var(--nk-border-strong)] hover:bg-[var(--nk-raised)] hover:text-[var(--nk-text)]"
                  onClick={() => onInsertPrompt(starter.prompt)}
                >
                  {starter.label}
                </button>
              ))}
            </div>
            <p className="mt-5 flex items-center gap-1.5 text-[10.5px] text-[var(--nk-ghost)]">
              <Command aria-hidden="true" className="h-3 w-3" />
              Gõ / để xem lệnh · Ctrl+K để tìm mọi phiên và lệnh
            </p>
          </section>
        ) : null}
        {useVirtual ? (
          <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
            {virtualizer.getVirtualItems().map((row) => {
              const message = session.messages[row.index];
              return (
                <div
                  key={message.id}
                  ref={measureVirtualRow}
                  data-index={row.index}
                  className="absolute left-0 top-0 w-full"
                  style={{ transform: `translateY(${row.start}px)` }}
                >
                  <MessageRow
                    message={message}
                    messageIndex={row.index}
                    onReady={focusPromptTarget}
                    streaming={session.status === "streaming" && message.id === lastMessage?.id}
                  />
                </div>
              );
            })}
          </div>
        ) : (
          session.messages.map((message, messageIndex) => (
            <MessageRow
              key={message.id}
              message={message}
              messageIndex={messageIndex}
              onReady={focusPromptTarget}
              streaming={session.status === "streaming" && message.id === lastMessage?.id}
            />
          ))
        )}
        {knowledgeContexts.map((context) => (
          <details
            key={context.contextId}
            className="my-2 rounded-xl border border-[var(--nk-border)] bg-[var(--nk-composer)] px-3 py-2"
            data-testid="knowledge-evidence"
          >
            <summary className="flex cursor-pointer list-none items-center gap-2 text-[11.5px] font-medium text-[var(--nk-text-2)]">
              <BookOpen aria-hidden="true" className="h-3.5 w-3.5 text-[var(--nk-accent)]" />
              Wiii Knowledge · {context.sources.length} nguồn đã đưa vào model
            </summary>
            <ol className="mt-2 v3-space-y-1 border-t border-[var(--nk-border)] pt-2 text-[10.5px] text-[var(--nk-text-3)]">
              {context.sources.map((source, index) => (
                <li key={source.sourceId} className="flex gap-2">
                  <span className="tabular-nums text-[var(--nk-text-2)]">[{index + 1}]</span>
                  <span className="min-w-0 truncate">
                    {source.title}
                    {source.documentId ? ` · ${source.documentId}` : ""}
                    {source.pageNumber > 0 ? ` · trang ${source.pageNumber}` : ""}
                  </span>
                </li>
              ))}
            </ol>
          </details>
        ))}
        {session.pendingPermission ? (
          <PermissionCard
            session={session}
            request={session.pendingPermission}
            resolving={session.resolvingPermissionId === session.pendingPermission.requestId}
            blockedByCancel={session.cancelPending}
            onResolve={onResolvePermission}
          />
        ) : null}
        {session.status === "streaming" && !session.pendingPermission && !controlNotices.some((notice) => notice.kind === "cancel" || notice.kind === "unknown") ? (
          <p
            className="my-2 flex items-center gap-2 text-[12.5px] text-[var(--nk-text-3)]"
            data-testid="neko-working-state"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--nk-accent)] nk-status-pulse" />
            {streamingActivityLabel(session)}
          </p>
        ) : null}
        <SessionControlStatus session={session} notices={controlNotices} onRecover={onRecover}
          onRetry={onRetry ? async (eventId) => {
            updateFollowingTail(true);
            scrollToLatest();
            scrollRef.current?.focus({ preventScroll: true });
            await onRetry(eventId);
          } : undefined} />
        <div ref={bottomRef} />
      </div>
      </div>
      {!followingTail ? (
        <button
          type="button"
          className="absolute bottom-3 left-1/2 z-10 flex h-8 -translate-x-1/2 items-center gap-1.5 rounded-full border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] px-3 text-[11px] font-medium text-[var(--nk-text-2)] shadow-xs transition-colors hover:bg-[var(--nk-raised)] focus-visible:v3-outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
          onClick={() => {
            updateFollowingTail(true);
            const reducedMotion = typeof window.matchMedia === "function"
              && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            scrollToLatest(reducedMotion ? "auto" : "smooth");
            // The button disappears; keep focus on a stable, scrollable target.
            scrollRef.current?.focus({ preventScroll: true });
          }}
          aria-label="Đi tới tin nhắn mới nhất"
        >
          <ArrowDown aria-hidden="true" className="h-3.5 w-3.5" />
          Mới nhất
        </button>
      ) : null}
    </div>
  );
}
