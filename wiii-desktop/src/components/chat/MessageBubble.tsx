/**
 * MessageBubble — professional UI with interleaved block support.
 * Sprint 62: Interleaved thinking/answer rendering.
 * Sprint 81: Message action bar, timestamps, regenerate/edit/feedback.
 */
import { useState, useCallback, memo } from "react";
import { motion } from "motion/react";
import { Copy, Check, RefreshCw, ThumbsUp, ThumbsDown, Pencil } from "lucide-react";
import type { Message, ContentBlock, ThinkingBlockData, ScreenshotBlockData, MoodType } from "@/api/types";
import type { SoulEmotionData } from "@/lib/avatar/types";
import type { AvatarState } from "@/lib/avatar/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { ThinkingBlock } from "./ThinkingBlock";
import { ActionText } from "./ActionText";
import { ScreenshotBlock } from "./ScreenshotBlock";
import { ThinkingTimeline } from "./ThinkingTimeline";
import { SourceCitation } from "./SourceCitation";
import { SuggestedQuestions } from "./SuggestedQuestions";
import { ReasoningTrace } from "./ReasoningTrace";
import { useSettingsStore } from "@/stores/settings-store";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { submitFeedback } from "@/api/feedback";
import { formatRelativeTime, formatAbsoluteTime } from "@/lib/date-utils";
import { userMessageEntry, aiMessageEntry } from "@/lib/animations";
import { useReducedMotion, motionSafe } from "@/hooks/useReducedMotion";

interface MessageBubbleProps {
  message: Message;
  isLastAssistant?: boolean;
  /** Live avatar state — only passed for the latest assistant message */
  liveAvatarState?: AvatarState;
  liveAvatarMood?: MoodType;
  liveSoulEmotion?: SoulEmotionData | null;
  onSuggestedQuestion?: (q: string) => void;
  onRegenerate?: () => void;
  onEditMessage?: (content: string) => void;
}

export const MessageBubble = memo(function MessageBubble({
  message,
  isLastAssistant,
  liveAvatarState,
  liveAvatarMood,
  liveSoulEmotion,
  onSuggestedQuestion,
  onRegenerate,
  onEditMessage,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const reduced = useReducedMotion();
  const { show_thinking, show_reasoning_trace, thinking_level } = useSettingsStore(
    (s) => s.settings
  );

  if (isUser) {
    return (
      <motion.div
        className="flex justify-end group/msg"
        variants={motionSafe(reduced, userMessageEntry)}
        initial={reduced ? false : "hidden"}
        animate="visible"
      >
        <div className="max-w-[85%]">
          <div className="bg-[var(--user-bg)] rounded-xl px-4 py-2.5 relative">
            <p className="text-[15px] leading-[1.7] font-sans text-text selectable">
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

  // Extract mood from message metadata (saved at finalize time)
  const messageMood: MoodType | undefined = (() => {
    const md = message.metadata?.mood as { mood?: string } | undefined;
    const m = md?.mood;
    const valid: string[] = ["excited", "warm", "concerned", "gentle", "neutral"];
    return valid.includes(m ?? "") ? (m as MoodType) : undefined;
  })();

  // Assistant message
  const blocks = message.blocks;
  const hasBlocks = blocks && blocks.length > 0;

  return (
    <motion.div
      className="flex gap-2.5 group/msg"
      variants={motionSafe(reduced, aiMessageEntry)}
      initial={reduced ? false : "hidden"}
      animate="visible"
    >
      {/* Wiii avatar — latest: 64px kawaii face (live state), older: 24px "W" logo */}
      {isLastAssistant ? (
        <motion.div layoutId="wiii-active-avatar">
          <WiiiAvatar
            state={liveAvatarState ?? "idle"}
            size={64}
            mood={liveAvatarMood ?? messageMood}
            soulEmotion={liveSoulEmotion}
          />
        </motion.div>
      ) : (
        <WiiiAvatar state="idle" size={24} mood={messageMood} />
      )}

      <div className="flex-1 min-w-0">
        {hasBlocks ? (
          <BlockRenderer
            blocks={blocks}
            showThinking={show_thinking}
            thinkingLevel={thinking_level}
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
 * Block-based renderer — interleaved thinking + answer (Opus pattern).
 *
 * Sprint 146: Each thinking block rendered independently, interleaved with
 * answer blocks in their original order.
 *
 * Sprint 149 "Dòng Chảy Tư Duy":
 * - 0-2 thinking+action_text blocks → render individually (backward compat)
 * - 3+ thinking+action_text blocks → group into ThinkingTimeline
 * - Segments: consecutive thinking+action_text → timeline, answer → inline
 */
function BlockRenderer({
  blocks,
  showThinking,
  thinkingLevel = "balanced",
  message: _message,
}: {
  blocks: ContentBlock[];
  showThinking: boolean;
  thinkingLevel?: import("@/api/types").ThinkingLevel;
  message: Message;
}) {
  // If thinking hidden, only render answer blocks
  if (!showThinking || thinkingLevel === "minimal") {
    return (
      <>
        {blocks
          .filter((b) => b.type === "answer")
          .map((block) => (
            <div key={block.id} className="font-serif relative">
              <MarkdownRenderer content={block.content} />
            </div>
          ))}
      </>
    );
  }

  // Count thinking + action_text blocks
  const thinkingActionCount = blocks.filter(
    (b) => b.type === "thinking" || b.type === "action_text"
  ).length;

  // Simple path: 0-2 blocks → render individually (backward compat)
  if (thinkingActionCount < 3) {
    return (
      <>
        {blocks.map((block) => {
          if (block.type === "thinking") {
            const tb = block as ThinkingBlockData;
            return (
              <ThinkingBlock
                key={block.id}
                content={tb.content}
                toolCalls={tb.toolCalls}
                savedDuration={
                  tb.startTime && tb.endTime
                    ? Math.round((tb.endTime - tb.startTime) / 1000)
                    : undefined
                }
                label={tb.label}
                summary={tb.summary || tb.label}
                thinkingLevel={thinkingLevel}
              />
            );
          }
          if (block.type === "action_text") {
            return <ActionText key={block.id} content={block.content} node={block.node} />;
          }
          if (block.type === "screenshot") {
            return <ScreenshotBlock key={block.id} block={block as ScreenshotBlockData} />;
          }
          if (block.type === "answer") {
            return (
              <div key={block.id} className="font-serif relative">
                <MarkdownRenderer content={block.content} />
              </div>
            );
          }
          return null;
        })}
      </>
    );
  }

  // Timeline path: 3+ blocks → segment into timeline groups + answer segments
  const segments: Array<
    | { kind: "timeline"; blocks: ContentBlock[]; key: string }
    | { kind: "answer"; block: ContentBlock }
  > = [];

  let currentTimeline: ContentBlock[] = [];

  for (const block of blocks) {
    if (block.type === "thinking" || block.type === "action_text") {
      currentTimeline.push(block);
    } else {
      // Flush accumulated timeline blocks
      if (currentTimeline.length > 0) {
        segments.push({
          kind: "timeline",
          blocks: currentTimeline,
          key: currentTimeline[0].id,
        });
        currentTimeline = [];
      }
      segments.push({ kind: "answer", block });
    }
  }
  // Flush remaining timeline blocks
  if (currentTimeline.length > 0) {
    segments.push({
      kind: "timeline",
      blocks: currentTimeline,
      key: currentTimeline[0].id,
    });
  }

  return (
    <>
      {segments.map((seg) => {
        if (seg.kind === "timeline") {
          return (
            <ThinkingTimeline
              key={seg.key}
              phases={seg.blocks}
              thinkingLevel={thinkingLevel}
            />
          );
        }
        if (seg.block.type === "screenshot") {
          return <ScreenshotBlock key={seg.block.id} block={seg.block as ScreenshotBlockData} />;
        }
        return (
          <div key={seg.block.id} className="font-serif relative">
            <MarkdownRenderer content={seg.block.content} />
          </div>
        );
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

      {/* Serif answer */}
      <div className="font-serif relative">
        <MarkdownRenderer content={message.content} />
      </div>
    </>
  );
}

