/**
 * MessageBubble — professional UI with interleaved block support.
 * Sprint 62: Interleaved thinking/answer rendering.
 * Sprint 81: Message action bar, timestamps, regenerate/edit/feedback.
 */
import { useState, useCallback, memo, Fragment } from "react";
import { motion } from "motion/react";
import { Copy, Check, RefreshCw, ThumbsUp, ThumbsDown, Pencil } from "lucide-react";
import type { Message, ContentBlock, ThinkingBlockData } from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { ThinkingBlock } from "./ThinkingBlock";
import { SourceCitation } from "./SourceCitation";
import { SuggestedQuestions } from "./SuggestedQuestions";
import { ReasoningTrace } from "./ReasoningTrace";
import { useSettingsStore } from "@/stores/settings-store";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { submitFeedback } from "@/api/feedback";
import { formatRelativeTime, formatAbsoluteTime } from "@/lib/date-utils";
import { userMessageEntry, aiMessageEntry } from "@/lib/animations";

interface MessageBubbleProps {
  message: Message;
  isLastAssistant?: boolean;
  onSuggestedQuestion?: (q: string) => void;
  onRegenerate?: () => void;
  onEditMessage?: (content: string) => void;
}

export const MessageBubble = memo(function MessageBubble({
  message,
  isLastAssistant,
  onSuggestedQuestion,
  onRegenerate,
  onEditMessage,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const { show_thinking, show_reasoning_trace } = useSettingsStore(
    (s) => s.settings
  );

  if (isUser) {
    return (
      <motion.div
        className="flex justify-end group/msg"
        variants={userMessageEntry}
        initial="hidden"
        animate="visible"
      >
        <div className="max-w-[85%]">
          <div className="bg-[var(--user-bg)] rounded-2xl rounded-br px-4 py-3 relative">
            <p className="text-[16px] leading-[1.6] font-serif text-text selectable">
              {message.content}
            </p>
            {/* User message actions */}
            {onEditMessage && (
              <div className="absolute -left-10 top-1/2 -translate-y-1/2 opacity-0 group-hover/msg:opacity-100 transition-opacity">
                <button
                  onClick={() => onEditMessage(message.content)}
                  className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-tertiary hover:text-text-secondary"
                  title="Chỉnh sửa"
                  aria-label="Chỉnh sửa tin nhắn"
                >
                  <Pencil size={14} />
                </button>
              </div>
            )}
          </div>
          {/* Timestamp */}
          {message.timestamp && (
            <div
              className="mt-0.5 text-right text-[10px] text-text-tertiary opacity-0 group-hover/msg:opacity-100 transition-opacity"
              title={formatAbsoluteTime(message.timestamp)}
            >
              {formatRelativeTime(message.timestamp)}
            </div>
          )}
        </div>
      </motion.div>
    );
  }

  // Assistant message
  const blocks = message.blocks;
  const hasBlocks = blocks && blocks.length > 0;

  return (
    <motion.div
      className="flex gap-2.5 group/msg"
      variants={aiMessageEntry}
      initial="hidden"
      animate="visible"
    >
      {/* Wiii avatar — living presence */}
      <WiiiAvatar state="complete" />

      <div className="flex-1 min-w-0">
        {hasBlocks ? (
          <BlockRenderer
            blocks={blocks}
            showThinking={show_thinking}
            message={message}
          />
        ) : (
          <LegacyRenderer
            message={message}
            showThinking={show_thinking}
          />
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <SourceCitation sources={message.sources} />
        )}

        {/* Domain notice — gentle indicator for off-domain content */}
        {message.domain_notice && (
          <div className="mt-2 px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 text-xs text-amber-700 dark:text-amber-400 flex items-center gap-2">
            <span className="text-amber-500">&#x1F4A1;</span>
            <span>{message.domain_notice}</span>
          </div>
        )}

        {/* Reasoning trace — guarded by setting */}
        {show_reasoning_trace && message.reasoning_trace && (
          <ReasoningTrace trace={message.reasoning_trace} />
        )}

        {/* Metadata + action bar row */}
        <div className="mt-2 flex items-center gap-2">
          {/* Metadata */}
          {message.metadata && (
            <div className="flex items-center gap-3 text-[11px] text-text-tertiary">
              {typeof message.metadata.agent_type === "string" && (
                <span className="px-1.5 py-0.5 rounded bg-[var(--surface-tertiary)]">
                  {message.metadata.agent_type}
                </span>
              )}
              {typeof message.metadata.processing_time === "number" && (
                <span>{(message.metadata.processing_time as number).toFixed(1)}s</span>
              )}
              {typeof message.metadata.model === "string" && (
                <span>{message.metadata.model as string}</span>
              )}
            </div>
          )}

          {/* Action bar */}
          <MessageActions
            message={message}
            isLastAssistant={isLastAssistant}
            onRegenerate={onRegenerate}
          />
        </div>

        {/* Timestamp */}
        {message.timestamp && (
          <div
            className="mt-0.5 text-[10px] text-text-tertiary opacity-0 group-hover/msg:opacity-100 transition-opacity"
            title={formatAbsoluteTime(message.timestamp)}
          >
            {formatRelativeTime(message.timestamp)}
          </div>
        )}

        {/* Suggested questions */}
        {message.suggested_questions &&
          message.suggested_questions.length > 0 &&
          onSuggestedQuestion && (
            <SuggestedQuestions
              questions={message.suggested_questions}
              onSelect={onSuggestedQuestion}
            />
          )}
      </div>
    </motion.div>
  );
});

/**
 * Message action bar — copy, regenerate, feedback.
 * Sprint 107: Feedback persisted locally + sent to backend.
 */
function MessageActions({
  message,
  isLastAssistant,
  onRegenerate,
}: {
  message: Message;
  isLastAssistant?: boolean;
  onRegenerate?: () => void;
}) {
  const { addToast } = useToastStore();
  const setMessageFeedback = useChatStore((s) => s.setMessageFeedback);
  const activeConv = useChatStore((s) => s.activeConversation());
  const [copied, setCopied] = useState(false);

  // Use persisted feedback from message, not local state
  const feedback = message.feedback ?? null;

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      addToast("success", "Đã sao chép tin nhắn!");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-secure contexts
    }
  }, [message.content, addToast]);

  const handleFeedback = useCallback(
    (rating: "up" | "down") => {
      const newRating = feedback === rating ? null : rating;
      // Persist locally
      setMessageFeedback(message.id, newRating);
      // Send to backend (fire-and-forget)
      const sessionId = activeConv?.session_id || activeConv?.id || "";
      if (newRating && sessionId) {
        submitFeedback(message.id, sessionId, newRating).catch(() => {
          // Silent: local persistence is the primary store
        });
      }
    },
    [feedback, message.id, activeConv, setMessageFeedback]
  );

  return (
    <div className="flex items-center gap-0.5 opacity-0 group-hover/msg:opacity-100 transition-opacity ml-auto">
      {/* Copy */}
      <motion.button
        onClick={handleCopy}
        className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-tertiary hover:text-text-secondary transition-colors"
        title="Sao chép"
        aria-label="Sao chép tin nhắn"
        whileHover={{ scale: 1.15 }}
        whileTap={{ scale: 0.9 }}
      >
        {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
      </motion.button>

      {/* Regenerate — only on last assistant message */}
      {isLastAssistant && onRegenerate && (
        <motion.button
          onClick={onRegenerate}
          className="p-1.5 rounded-md hover:bg-surface-tertiary text-text-tertiary hover:text-text-secondary transition-colors"
          title="Tạo lại"
          aria-label="Tạo lại phản hồi"
          whileHover={{ scale: 1.15, rotate: 15 }}
          whileTap={{ scale: 0.9 }}
        >
          <RefreshCw size={14} />
        </motion.button>
      )}

      {/* Thumbs up */}
      <motion.button
        onClick={() => handleFeedback("up")}
        className={`p-1.5 rounded-md hover:bg-surface-tertiary transition-colors ${
          feedback === "up" ? "text-green-500" : "text-text-tertiary hover:text-text-secondary"
        }`}
        title="Phản hồi tốt"
        aria-label="Đánh giá tốt"
        whileHover={{ scale: 1.15, y: -2 }}
        whileTap={{ scale: 0.9 }}
      >
        <ThumbsUp size={14} />
      </motion.button>

      {/* Thumbs down */}
      <motion.button
        onClick={() => handleFeedback("down")}
        className={`p-1.5 rounded-md hover:bg-surface-tertiary transition-colors ${
          feedback === "down" ? "text-red-500" : "text-text-tertiary hover:text-text-secondary"
        }`}
        title="Phản hồi chưa tốt"
        aria-label="Đánh giá chưa tốt"
        whileHover={{ scale: 1.15, y: 2 }}
        whileTap={{ scale: 0.9 }}
      >
        <ThumbsDown size={14} />
      </motion.button>
    </div>
  );
}

/**
 * Block-based renderer — supports interleaved thinking + answer.
 * DoneRow appears before the last answer block if there was any thinking.
 */
function BlockRenderer({
  blocks,
  showThinking,
  message: _message,
}: {
  blocks: ContentBlock[];
  showThinking: boolean;
  message: Message;
}) {
  // Find the index of the last answer block
  let lastAnswerIndex = -1;
  for (let i = blocks.length - 1; i >= 0; i--) {
    if (blocks[i].type === "answer") {
      lastAnswerIndex = i;
      break;
    }
  }
  const hasThinking = blocks.some((b) => b.type === "thinking");

  return (
    <>
      {blocks.map((block, i) => {
        if (block.type === "thinking") {
          if (!showThinking) return null;
          const tb = block as ThinkingBlockData;
          const duration = tb.startTime && tb.endTime
            ? Math.round((tb.endTime - tb.startTime) / 1000)
            : undefined;
          return (
            <ThinkingBlock
              key={i}
              content={tb.content}
              toolCalls={tb.toolCalls}
              savedDuration={duration}
              label={tb.label}
            />
          );
        }

        if (block.type === "answer") {
          const isLastAnswer = i === lastAnswerIndex;
          return (
            <Fragment key={i}>
              {isLastAnswer && hasThinking && <DoneRow />}
              <div className="font-serif relative">
                <MarkdownRenderer content={block.content} />
              </div>
            </Fragment>
          );
        }

        return null;
      })}
    </>
  );
}

/**
 * Legacy renderer — for messages without blocks (pre-Sprint 62 or simple).
 */
function LegacyRenderer({
  message,
  showThinking,
}: {
  message: Message;
  showThinking: boolean;
}) {
  return (
    <>
      {/* ThinkingBlock with inline tool cards */}
      {showThinking && (message.thinking || (message.tool_calls && message.tool_calls.length > 0)) && (
        <ThinkingBlock
          content={message.thinking || ""}
          savedDuration={
            message.metadata?.processing_time
              ? Math.round(Number(message.metadata.processing_time))
              : undefined
          }
          toolCalls={message.tool_calls}
        />
      )}

      {/* DoneRow before answer */}
      {message.content && <DoneRow />}

      {/* Serif answer */}
      <div className="font-serif relative">
        <MarkdownRenderer content={message.content} />
      </div>
    </>
  );
}

function DoneRow() {
  return (
    <div className="flex items-center gap-1.5 py-1 my-1">
      <svg className="done-anim" width="17" height="17" viewBox="0 0 20 20" fill="none">
        <circle
          cx="10"
          cy="10"
          r="9"
          stroke="var(--accent-green)"
          strokeWidth="1.5"
          fill="none"
        />
        <path
          d="M6 10.5l2.5 2.5 5-6"
          stroke="var(--accent-green)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
      <span className="text-[13px] text-text-tertiary">Done</span>
    </div>
  );
}
