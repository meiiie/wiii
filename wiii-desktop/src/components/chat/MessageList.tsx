/**
 * MessageList — renders conversation messages + streaming state.
 * Sprint 81: Scroll-to-bottom FAB, message actions, regenerate.
 */
import { ChevronDown } from "lucide-react";
import type { Message, ThinkingBlockData } from "@/api/types";
import { useChatStore } from "@/stores/chat-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { MessageBubble } from "./MessageBubble";
import { StreamingIndicator } from "./StreamingIndicator";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { ThinkingBlock } from "./ThinkingBlock";
import { SourceCitation } from "./SourceCitation";

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
    streamingSteps,
  } = useChatStore();

  const { show_thinking } = useSettingsStore((s) => s.settings);

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

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-6 scroll-container"
        aria-live="polite"
      >
        <div className="max-w-3xl mx-auto space-y-5">
          {messages.map((msg, idx) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              isLastAssistant={idx === lastAssistantIdx && msg.role === "assistant"}
              onSuggestedQuestion={onSuggestedQuestion}
              onRegenerate={idx === lastAssistantIdx ? onRegenerate : undefined}
              onEditMessage={msg.role === "user" ? onEditMessage : undefined}
            />
          ))}

          {/* Streaming message — avatar + interleaved blocks */}
          {isStreaming && (
            <div className="flex gap-2.5 animate-slide-in">
              {/* Wiii avatar — thinking until answer starts, then speaking */}
              <WiiiAvatar state={streamingContent ? "speaking" : "thinking"} />

              <div className="flex-1 min-w-0">
                {/* Always show progress panel */}
                <StreamingIndicator
                  steps={streamingSteps}
                  startTime={streamingStartTime}
                  currentStep={streamingStep}
                />

                {/* Render streaming blocks in order */}
                {streamingBlocks.map((block, i) => {
                  const isLastBlock = i === streamingBlocks.length - 1;

                  if (block.type === "thinking") {
                    if (!show_thinking) return null;
                    const tb = block as ThinkingBlockData;
                    return (
                      <ThinkingBlock
                        key={i}
                        content={tb.content}
                        toolCalls={tb.toolCalls}
                        isStreaming={isLastBlock && !tb.endTime}
                        label={tb.label}
                        savedDuration={
                          tb.startTime && tb.endTime
                            ? Math.round((tb.endTime - tb.startTime) / 1000)
                            : undefined
                        }
                      />
                    );
                  }

                  if (block.type === "answer") {
                    return (
                      <div key={i} className="font-serif">
                        <MarkdownRenderer content={block.content} />
                        {isLastBlock && (
                          <span className="inline-block w-[2px] h-[1em] bg-[var(--accent-orange)] ml-0.5 align-middle animate-pulse rounded-sm" />
                        )}
                      </div>
                    );
                  }

                  return null;
                })}

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
          )}
        </div>
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
