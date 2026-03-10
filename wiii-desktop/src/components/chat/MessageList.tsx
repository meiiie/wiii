import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown } from "lucide-react";
import type { ContentBlock, Message } from "@/api/types";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useAvatarState } from "@/hooks/useAvatarState";
import { MessageBubble } from "./MessageBubble";
import { InterleavedBlockSequence } from "./InterleavedBlockSequence";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { SourceCitation } from "./SourceCitation";

const VIRTUALIZATION_THRESHOLD = 50;
const MESSAGE_GAP = 20;

function getVisibleStreamingBlocks(
  blocks: ContentBlock[],
  showThinking: boolean,
  thinkingLevel: string,
): ContentBlock[] {
  const includeThinking = showThinking && thinkingLevel !== "minimal";
  return blocks.filter((block) => includeThinking || !["thinking", "action_text", "tool_execution"].includes(block.type));
}

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
    streamingSources,
    streamingContent,
    streamingStartTime,
  } = useChatStore();

  const { show_thinking, thinking_level } = useSettingsStore((s) => s.settings);
  const { state: avatarState, mood: avatarMood, soulEmotion } = useAvatarState();
  const visibleStreamingBlocks = getVisibleStreamingBlocks(streamingBlocks, show_thinking, thinking_level);

  const { containerRef, scrollToBottom, isAtBottom } = useAutoScroll(
    isStreaming ? streamingContent : messages.length,
  );

  let lastAssistantIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") {
      lastAssistantIdx = i;
      break;
    }
  }

  const useVirtual = messages.length > VIRTUALIZATION_THRESHOLD;
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => containerRef.current,
    estimateSize: useCallback((index: number) => (
      messages[index]?.role === "user" ? 70 : 200
    ), [messages]),
    overscan: 5,
    gap: MESSAGE_GAP,
    enabled: useVirtual,
  });

  return (
    <div className="relative flex-1 overflow-hidden chat-stage">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-6 scroll-container chat-stage__scroller"
        aria-live={isStreaming ? "off" : "polite"}
      >
        {useVirtual ? (
          <div className="chat-lane">
            <div style={{ height: virtualizer.getTotalSize(), position: "relative", width: "100%" }}>
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
          <div className="chat-lane space-y-5">
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

        {isStreaming && (
          <div className="chat-lane mt-5">
            <div className="flex gap-2.5 animate-slide-in">
              <motion.div layoutId="wiii-active-avatar">
                <WiiiAvatar state={avatarState} size={64} mood={avatarMood} soulEmotion={soulEmotion} />
              </motion.div>

              <div className="flex-1 min-w-0">
                <InterleavedBlockSequence
                  blocks={visibleStreamingBlocks}
                  showThinking={show_thinking}
                  thinkingLevel={thinking_level}
                  isStreaming
                />

                {streamingStartTime && (
                  <StreamingTimer startTime={streamingStartTime} />
                )}

                {streamingSources && streamingSources.length > 0 && (
                  <SourceCitation sources={streamingSources} />
                )}

                {onCancel && (
                  <button
                    onClick={onCancel}
                    className="mt-2 px-3 py-1 rounded-lg border border-border text-xs text-text-secondary hover:bg-surface-tertiary transition-colors"
                  >
                    Dung Wiii
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {!isAtBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 right-4 w-9 h-9 rounded-full bg-surface border border-border shadow-lg flex items-center justify-center text-text-secondary hover:text-text hover:bg-surface-secondary transition-all animate-fade-in"
          title="Cuon xuong cuoi"
          aria-label="Cuon xuong cuoi"
        >
          <ChevronDown size={18} />
        </button>
      )}
    </div>
  );
}

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
