/**
 * MessageList — renders conversation messages + streaming state.
 * Sprint 81: Scroll-to-bottom FAB, message actions, regenerate.
 * Sprint 141b: Interleaved thinking+answer blocks ("Tự Vấn").
 * Sprint 162b: Virtual scrolling via @tanstack/react-virtual (>50 messages).
 */
import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown } from "lucide-react";
import type { Message, ThinkingBlockData, ScreenshotBlockData } from "@/api/types";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useAvatarState } from "@/hooks/useAvatarState";
import { MessageBubble } from "./MessageBubble";
import { ThinkingBlock } from "./ThinkingBlock";
import { ActionText } from "./ActionText";
import { ScreenshotBlock } from "./ScreenshotBlock";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { SourceCitation } from "./SourceCitation";

/** Virtualize only when message count exceeds this threshold */
const VIRTUALIZATION_THRESHOLD = 50;
/** Gap between message items (space-y-5 = 20px) */
const MESSAGE_GAP = 20;

interface MessageListProps {
  messages: Message[];
  onSuggestedQuestion: (q: string) => void;
  onCancel?: () => void;
  onRegenerate?: () => void;
  onEditMessage?: (content: string) => void;
}

export function MessageList({
  messages,
  onSuggestedQuestion,
  onCancel,
  onRegenerate,
  onEditMessage,
}: MessageListProps) {
  const {
    isStreaming,
    streamingBlocks,
    streamingStep,
    streamingSources,
    streamingContent,
    streamingStartTime,
  } = useChatStore();

  const { show_thinking, thinking_level } = useSettingsStore((s) => s.settings);
  const { state: avatarState, mood: avatarMood, soulEmotion } = useAvatarState();

  const { containerRef, scrollToBottom, isAtBottom } = useAutoScroll(
    isStreaming ? streamingContent : messages.length
  );

  // Find last assistant message index for regenerate button
  let lastAssistantIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") {
      lastAssistantIdx = i;
      break;
    }
  }

  const useVirtual = messages.length > VIRTUALIZATION_THRESHOLD;

  // Virtual scrolling for large conversations
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => containerRef.current,
    estimateSize: useCallback((index: number) => {
      // Rough estimate: user messages ~60px, assistant ~200px
      return messages[index]?.role === "user" ? 70 : 200;
    }, [messages]),
    overscan: 5,
    gap: MESSAGE_GAP,
    enabled: useVirtual,
  });

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-6 scroll-container"
        aria-live={isStreaming ? "off" : "polite"}
      >
        {useVirtual ? (
          /* Virtualized path — only render visible messages */
          <div className="max-w-[720px] mx-auto">
            <div
              style={{ height: virtualizer.getTotalSize(), position: "relative", width: "100%" }}
            >
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const msg = messages[virtualRow.index];
                const isLast = virtualRow.index === lastAssistantIdx && msg.role === "assistant";
                return (
                  <div
                    key={msg.id}
                    data-index={virtualRow.index}
                    ref={virtualizer.measureElement}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <MessageBubble
                      message={msg}
                      isLastAssistant={isLast}
                      liveAvatarState={isLast ? avatarState : undefined}
                      liveAvatarMood={isLast ? avatarMood : undefined}
                      liveSoulEmotion={isLast ? soulEmotion : undefined}
                      onSuggestedQuestion={onSuggestedQuestion}
                      onRegenerate={isLast ? onRegenerate : undefined}
                      onEditMessage={msg.role === "user" ? onEditMessage : undefined}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Standard path — render all messages (< threshold) */
          <div className="max-w-[720px] mx-auto space-y-5">
            {messages.map((msg, idx) => {
              const isLast = idx === lastAssistantIdx && msg.role === "assistant";
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isLastAssistant={isLast}
                  liveAvatarState={isLast ? avatarState : undefined}
                  liveAvatarMood={isLast ? avatarMood : undefined}
                  liveSoulEmotion={isLast ? soulEmotion : undefined}
                  onSuggestedQuestion={onSuggestedQuestion}
                  onRegenerate={isLast ? onRegenerate : undefined}
                  onEditMessage={msg.role === "user" ? onEditMessage : undefined}
                />
              );
            })}
          </div>
        )}

        {/* Streaming message — avatar + interleaved blocks (always rendered) */}
        {isStreaming && (
          <div className="max-w-[720px] mx-auto mt-5">
            <div className="flex gap-2.5 animate-slide-in">
              {/* Wiii avatar — 64px kawaii face for active streaming (newest message) */}
              <motion.div layoutId="wiii-active-avatar">
                <WiiiAvatar state={avatarState} size={64} mood={avatarMood} soulEmotion={soulEmotion} />
              </motion.div>

              <div className="flex-1 min-w-0">
                {/* Sprint 146: Interleaved thinking+answer — Opus pattern */}
                {streamingBlocks.map((block, i) => {
                  if (block.type === "thinking") {
                    if (!show_thinking || thinking_level === "minimal") return null;
                    const tb = block as ThinkingBlockData;
                    return (
                      <ThinkingBlock
                        key={block.id}
                        content={tb.content}
                        toolCalls={tb.toolCalls}
                        label={tb.label}
                        summary={tb.summary || tb.label}
                        isStreaming={!tb.endTime}
                        thinkingLevel={thinking_level}
                      />
                    );
                  }
                  if (block.type === "action_text") {
                    return (
                      <ActionText key={block.id} content={block.content} node={block.node} />
                    );
                  }
                  if (block.type === "screenshot") {
                    return <ScreenshotBlock key={block.id} block={block as ScreenshotBlockData} />;
                  }
                  if (block.type === "answer") {
                    const isLastAnswer = !streamingBlocks.slice(i + 1).some(b => b.type === "answer");
                    return (
                      <div key={block.id} className="font-serif">
                        <MarkdownRenderer content={block.content} />
                        {isLastAnswer && isStreaming && (
                          <span className="inline-block w-[2px] h-[1em] bg-[var(--accent-orange)] ml-0.5 align-middle animate-pulse rounded-sm" />
                        )}
                      </div>
                    );
                  }
                  return null;
                })}

                {/* Minimal mode: current step indicator */}
                {(thinking_level === "minimal" || !show_thinking) && streamingStep && !streamingContent && (
                  <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-2">
                    <span className="w-2 h-2 rounded-full bg-[var(--accent-orange)] animate-pulse" />
                    <span>{streamingStep}</span>
                  </div>
                )}

                {/* Overall timer — during streaming */}
                {streamingStartTime && (
                  <StreamingTimer startTime={streamingStartTime} />
                )}

                {/* Sources during streaming */}
                {streamingSources && streamingSources.length > 0 && (
                  <SourceCitation sources={streamingSources} />
                )}

                {/* Stop button */}
                {onCancel && (
                  <button
                    onClick={onCancel}
                    className="mt-2 px-3 py-1 rounded-lg border border-border text-xs
                               text-text-secondary hover:bg-surface-tertiary transition-colors"
                  >
                    ■ Dừng Wiii
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scroll-to-bottom FAB */}
      {!isAtBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 w-9 h-9 rounded-full bg-surface border border-border shadow-lg flex items-center justify-center text-text-secondary hover:text-text hover:bg-surface-secondary transition-all animate-fade-in"
          title="Cuộn xuống cuối"
          aria-label="Cuộn xuống cuối"
        >
          <ChevronDown size={18} />
        </button>
      )}
    </div>
  );
}

/** Compact streaming timer — shows elapsed time during streaming */
function StreamingTimer({ startTime }: { startTime: number }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(Math.floor((Date.now() - startTime) / 1000));
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  return (
    <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-text-tertiary animate-pulse">
      <span className="tabular-nums">
        {elapsed >= 60
          ? `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`
          : `${elapsed}s`}
      </span>
    </div>
  );
}
