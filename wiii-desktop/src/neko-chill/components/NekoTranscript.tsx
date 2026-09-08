/**
 * Neko Chill transcript — workspace-shell styling (#904): 780px
 * centered column, quiet thinking rail, dot-status tool rows, shared
 * MarkdownRenderer for answers, with measured row virtualization for long sessions.
 */
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, BookOpen, ChevronRight, Command, FolderGit2 } from "lucide-react";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { NekoActivityIcon, resolveNekoToolIconKind } from "@/components/icons/neko";
import type { ContentBlock, ThinkingBlockData, ToolExecutionBlockData } from "@/api/types";
import type { NekoSession } from "../stores/neko-session-store";
import { PermissionCard } from "./PermissionCard";
import { NekoPromptRail, type NekoPromptLandmark } from "./NekoPromptRail";

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

/** Remove one matching outer emphasis pair without interpreting reasoning as HTML. */
export function formatReasoningLabel(content: string): string {
  const trimmed = content.trim();
  for (const marker of ["**", "__", "*", "_"]) {
    if (
      trimmed.length > marker.length * 2 &&
      trimmed.startsWith(marker) &&
      trimmed.endsWith(marker)
    ) {
      return trimmed.slice(marker.length, -marker.length).trim();
    }
  }
  return trimmed;
}

export function formatReasoningPreview(content: string, maxLength = 112): string {
  const compact = formatReasoningLabel(content).replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) return compact;
  return `${compact.slice(0, Math.max(1, maxLength - 1)).trimEnd()}…`;
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
  const label = block.label || block.summary || block.phase || (active ? "Đang suy nghĩ" : "Đã suy nghĩ");
  const preview = formatReasoningPreview(block.content);
  const duration = formatReasoningDuration(block);

  return (
    <details
      className="group my-0.5 min-w-0 max-w-full text-[12px] text-[var(--nk-text-3)]"
      data-testid="thinking-block"
    >
      <summary
        className="flex min-h-6 w-full min-w-0 cursor-pointer list-none items-center gap-2 overflow-hidden rounded-md px-1 outline-none transition-colors hover:bg-[var(--nk-inset)] focus-visible:ring-2 focus-visible:ring-[var(--nk-focus)] [&::-webkit-details-marker]:hidden"
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
        {preview && preview !== label ? (
          <span
            className="min-w-0 flex-1 truncate text-[var(--nk-ghost)]"
            data-testid="thinking-preview"
          >
            · {preview}
          </span>
        ) : null}
        {duration ? <span className="ml-auto shrink-0 tabular-nums">{duration}</span> : null}
        <ChevronRight
          aria-hidden="true"
          className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
        />
      </summary>
      <div className="ml-[7px] max-h-56 overflow-y-auto border-l border-[var(--nk-border)] py-1 pl-4 pr-2 text-[12px] leading-[18px] text-[var(--nk-text-3)]">
        <MarkdownRenderer content={block.content} />
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
        className="flex min-h-6 w-full min-w-0 cursor-pointer list-none items-center gap-2 overflow-hidden rounded-md px-1 outline-none transition-colors hover:bg-[var(--nk-inset)] focus-visible:ring-2 focus-visible:ring-[var(--nk-focus)] [&::-webkit-details-marker]:hidden"
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
        <ChevronRight
          aria-hidden="true"
          className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
        />
      </summary>
      <div className="ml-[7px] max-h-56 overflow-y-auto border-l border-[var(--nk-border)] py-1 pl-4 pr-2 text-[11.5px] leading-[18px]">
        <p className="break-words font-mono text-[var(--nk-text-2)]">{block.tool.name}</p>
        {block.tool.result ? (
          <p className="mt-1 whitespace-pre-wrap break-words text-[var(--nk-text-3)]">{block.tool.result}</p>
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
        className="flex min-h-6 w-full min-w-0 cursor-pointer list-none items-center gap-2 overflow-hidden rounded-md px-1 outline-none transition-colors hover:bg-[var(--nk-inset)] focus-visible:ring-2 focus-visible:ring-[var(--nk-focus)] [&::-webkit-details-marker]:hidden"
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
        <span className="min-w-0 flex-1 truncate text-[var(--nk-ghost)]">· {summary}</span>
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
      return <MarkdownRenderer content={block.content} className="my-2 text-[13.5px]" />;
    default:
      // Cloud-only block kinds never arrive from local drivers in v0.
      return null;
  }
}

const MessageRow = memo(function MessageRow({
  message,
  messageIndex,
  streaming = false,
}: {
  message: NekoSession["messages"][number];
  messageIndex: number;
  streaming?: boolean;
}) {
  const blocks = message.blocks ?? [];
  const lastBlock = blocks[blocks.length - 1];
  const groups = groupTranscriptBlocks(blocks);
  return message.role === "user" ? (
    <div
      className="my-3 flex scroll-mt-6 justify-end"
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
        <Block key={group.block.id} block={group.block} />
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

interface NekoTranscriptProps {
  session: NekoSession;
  onResolvePermission: (optionId: string | null) => void;
  onInsertPrompt: (text: string) => void;
}

const STARTER_PROMPTS = [
  {
    label: "Kiểm tra dự án này",
    prompt: "Kiểm tra dự án này và cho tôi biết điểm cần chú ý.",
  },
  {
    label: "Tóm tắt cấu trúc",
    prompt: "Tóm tắt cấu trúc dự án và đề xuất bước tiếp theo.",
  },
];

export function NekoTranscript({
  session,
  onResolvePermission,
  onInsertPrompt,
}: NekoTranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef(session.messages);
  messagesRef.current = session.messages;
  const [followingTail, setFollowingTail] = useState(true);
  const followingTailRef = useRef(true);
  const messageCount = session.messages.length;
  const lastMessage = session.messages[messageCount - 1];
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
  });

  const updateFollowingTail = useCallback((next: boolean) => {
    if (followingTailRef.current === next) return;
    followingTailRef.current = next;
    setFollowingTail(next);
  }, []);

  const scrollToLatest = useCallback(
    (behavior: ScrollBehavior = "auto") => {
      if (useVirtual && messageCount > 0) {
        virtualizer.scrollToIndex(messageCount - 1, { align: "end", behavior });
      } else if (typeof bottomRef.current?.scrollIntoView === "function") {
        bottomRef.current.scrollIntoView({ block: "end", behavior });
      }
    },
    [messageCount, useVirtual, virtualizer],
  );

  const jumpToPrompt = useCallback(
    (landmark: NekoPromptLandmark) => {
      const reducedMotion = typeof window.matchMedia === "function"
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const behavior: ScrollBehavior = reducedMotion ? "auto" : "smooth";
      updateFollowingTail(false);
      if (useVirtual) {
        virtualizer.scrollToIndex(landmark.messageIndex, { align: "start", behavior });
        return;
      }
      const target = scrollRef.current?.querySelector<HTMLElement>(
        `[data-neko-message-index="${landmark.messageIndex}"]`,
      );
      target?.scrollIntoView({ block: "start", behavior });
    },
    [updateFollowingTail, useVirtual, virtualizer],
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

  useEffect(() => {
    updateFollowingTail(true);
  }, [session.id, updateFollowingTail]);

  useEffect(() => {
    if (lastMessage?.role === "user") updateFollowingTail(true);
  }, [lastMessage?.id, lastMessage?.role, updateFollowingTail]);

  useEffect(() => {
    if (!followingTail) return;
    const frame = requestAnimationFrame(() => scrollToLatest());
    return () => cancelAnimationFrame(frame);
  }, [followingTail, lastBlockCount, messageCount, scrollToLatest, session.pendingPermission]);

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scrollRef}
        className="nk-scroll-surface h-full min-w-0 overflow-x-hidden overflow-y-auto"
        data-testid="neko-transcript"
        role="log"
        aria-label="Lịch sử phiên Neko Chill"
        aria-live={session.status === "streaming" ? "off" : "polite"}
        onScroll={(event) => {
          const viewport = event.currentTarget;
          const distanceFromTail =
            viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
          updateFollowingTail(distanceFromTail < 96);
        }}
      >
      <div className="mx-auto min-w-0 w-full max-w-[780px] overflow-hidden py-4 pl-[58px] pr-5 min-[900px]:px-6">
        {session.messages.length === 0 && session.status === "idle" ? (
          <section className="mx-auto flex max-w-[560px] flex-col items-center px-4 py-[10vh] text-center" aria-label="Bắt đầu phiên">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--nk-inset)] text-[var(--nk-text-2)]">
              <FolderGit2 aria-hidden="true" className="h-[18px] w-[18px]" />
            </span>
            <h2 className="mt-4 text-[18px] font-medium tracking-[-0.02em] text-[var(--nk-text)]">
              Sẵn sàng trong {session.workspace?.name ?? "dự án này"}
            </h2>
            <p className="mt-1.5 max-w-[460px] text-[12.5px] leading-5 text-[var(--nk-text-3)]">
              Agent chỉ làm việc trong thư mục đã chọn. Hãy mô tả kết quả bạn muốn;
              các gợi ý dưới đây chỉ được chèn vào ô soạn để bạn xem lại.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {STARTER_PROMPTS.map((starter) => (
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
                  ref={virtualizer.measureElement}
                  data-index={row.index}
                  className="absolute left-0 top-0 w-full"
                  style={{ transform: `translateY(${row.start}px)` }}
                >
                  <MessageRow
                    message={message}
                    messageIndex={row.index}
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
            <ol className="mt-2 space-y-1 border-t border-[var(--nk-border)] pt-2 text-[10.5px] text-[var(--nk-text-3)]">
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
            request={session.pendingPermission}
            resolving={session.resolvingPermissionId === session.pendingPermission.requestId}
            blockedByCancel={session.cancelPending}
            onResolve={onResolvePermission}
          />
        ) : null}
        {session.status === "streaming" && !session.pendingPermission ? (
          <p
            className="my-2 flex items-center gap-2 text-[12.5px] text-[var(--nk-text-3)]"
            data-testid="neko-working-state"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--nk-accent)] nk-status-pulse" />
            {streamingActivityLabel(session)}
          </p>
        ) : null}
        {session.status === "error" ? (
          <p className="my-2 text-[12.5px] text-[var(--nk-danger)]">{session.statusDetail}</p>
        ) : null}
        {session.status === "exited" && session.statusDetail ? (
          <p className="my-2 text-[12.5px] text-[var(--nk-text-3)]">{session.statusDetail}</p>
        ) : null}
        {session.status === "idle" && session.statusDetail ? (
          <p className="my-2 text-[12.5px] text-[var(--nk-warning)]">{session.statusDetail}</p>
        ) : null}
        <div ref={bottomRef} />
      </div>
      </div>
      <NekoPromptRail
        messages={promptRailMessages}
        scrollRef={scrollRef}
        resolveMessageOffset={resolveMessageOffset}
        onJump={jumpToPrompt}
      />
      {!followingTail ? (
        <button
          type="button"
          className="absolute bottom-3 left-1/2 z-10 flex h-8 -translate-x-1/2 items-center gap-1.5 rounded-full border border-[var(--nk-border-strong)] bg-[var(--nk-composer)] px-3 text-[11px] font-medium text-[var(--nk-text-2)] shadow-sm transition-colors hover:bg-[var(--nk-raised)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nk-focus-soft)]"
          onClick={() => {
            setFollowingTail(true);
            scrollToLatest("smooth");
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
