import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, Check, Copy, Clock, CheckCircle } from "lucide-react";
import type { ToolCallInfo } from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

import type { ThinkingLevel } from "@/api/types";

interface ThinkingBlockProps {
  content: string;
  isStreaming?: boolean;
  /** Duration in seconds — used for completed messages from history */
  savedDuration?: number;
  /** Tool calls to render inline inside the thinking block */
  toolCalls?: ToolCallInfo[];
  /** Custom label for the thinking header (e.g. "Phân tích câu hỏi") */
  label?: string;
  /** Sprint 145: One-line summary for collapsed header (Claude-like) */
  summary?: string;
  /** Sprint 140: Thinking display level — controls initial expand state */
  thinkingLevel?: ThinkingLevel;
}

/**
 * Claude-style thinking block — collapsed by default with summary header.
 *
 * Sprint 145 "Tư Duy Sâu":
 * - Collapsed: Clock/Check icon + summary text + duration + chevron
 * - Expanded: Simple step list with clock icons, no bordered card
 * - Default collapsed after completion, expandable on click
 * - Clean, minimal — matches Claude.ai thinking pattern
 */
export function ThinkingBlock({
  content,
  isStreaming = false,
  savedDuration,
  toolCalls,
  label: customLabel,
  summary,
  thinkingLevel = "balanced",
}: ThinkingBlockProps) {
  // detailed: always start expanded; streaming: expanded; balanced: collapsed
  const [expanded, setExpanded] = useState(
    thinkingLevel === "detailed" ? true : isStreaming
  );
  const [duration, setDuration] = useState(savedDuration || 0);
  const [copied, setCopied] = useState(false);
  const startTimeRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleCopy = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-secure contexts
    }
  }, [content]);

  // Timer for streaming mode
  useEffect(() => {
    if (isStreaming && !startTimeRef.current) {
      startTimeRef.current = Date.now();
      setExpanded(true);
      timerRef.current = setInterval(() => {
        if (startTimeRef.current) {
          setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }
      }, 1000);
    }

    if (!isStreaming && startTimeRef.current) {
      // Streaming ended — freeze timer
      if (timerRef.current) clearInterval(timerRef.current);
      setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
      startTimeRef.current = null;
      // Auto-collapse after a brief moment (skip for detailed mode)
      if (thinkingLevel !== "detailed") {
        const collapseTimer = setTimeout(() => setExpanded(false), 1500);
        return () => clearTimeout(collapseTimer);
      }
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isStreaming, thinkingLevel]);

  const hasContent = !!(content || (toolCalls && toolCalls.length > 0));
  const isComplete = !isStreaming;

  // Header text: prefer summary, then label, then default
  const headerText = summary || customLabel || "Tự Vấn";
  const durationText = duration > 0 ? `${duration}s` : (isStreaming ? "" : "");

  return (
    <div className="mb-1.5 group/thinking">
      {/* Header row — Claude-style collapsed/expanded toggle */}
      <div className="flex items-center">
        {hasContent ? (
          <button
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            className="flex items-center gap-1.5 text-[13px] text-text-tertiary hover:text-text-secondary transition-colors"
          >
            {/* Icon: CheckCircle when complete, Clock when streaming */}
            {isComplete ? (
              <CheckCircle size={14} className="text-[var(--accent-green)] shrink-0" />
            ) : (
              <Clock size={14} className="shrink-0 animate-pulse" />
            )}

            {/* Summary/label text */}
            <span className="font-medium truncate max-w-[400px]">{headerText}</span>

            {/* Duration */}
            {durationText && (
              <span className="text-text-tertiary tabular-nums">{durationText}</span>
            )}

            {/* Streaming dot */}
            {isStreaming && (
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
            )}

            {/* Chevron */}
            <ChevronDown
              size={14}
              className={`shrink-0 transition-transform duration-200 ${
                expanded ? "rotate-0" : "-rotate-90"
              }`}
            />
          </button>
        ) : (
          /* No content — just label + icon, no expand */
          <span className="flex items-center gap-1.5 text-[13px] text-text-tertiary">
            {isStreaming ? (
              <Clock size={14} className="animate-pulse" />
            ) : (
              <CheckCircle size={14} className="text-[var(--accent-green)]" />
            )}
            <span className="font-medium">{headerText}</span>
            {isStreaming && (
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)] animate-pulse" />
            )}
          </span>
        )}

        {/* Copy thinking content */}
        {content && !isStreaming && (
          <button
            onClick={handleCopy}
            className="ml-1 p-0.5 rounded text-text-tertiary opacity-0 group-hover/thinking:opacity-60 hover:!opacity-100 transition-opacity"
            title="Sao chép suy nghĩ"
            aria-label="Sao chép nội dung suy nghĩ"
          >
            {copied ? <Check size={12} className="text-[var(--accent-green)]" /> : <Copy size={12} />}
          </button>
        )}
      </div>

      {/* Expanded content — simple step list (no bordered card) */}
      {hasContent && (
        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <div className="pl-5 mt-1.5 space-y-0.5">
                {/* Thinking content as simple text steps */}
                {content && (
                  <div className="text-xs text-text-secondary leading-relaxed">
                    <MarkdownRenderer content={content} />
                    {isStreaming && (!toolCalls || toolCalls.length === 0) && (
                      <span className="inline-block w-1.5 h-3.5 bg-text-tertiary opacity-40 ml-0.5 animate-pulse rounded-sm" />
                    )}
                  </div>
                )}

                {/* Inline tool cards */}
                {toolCalls && toolCalls.length > 0 && (
                  <div className="mt-1 space-y-1">
                    {toolCalls.map((tc, i) => (
                      <InlineToolCard
                        key={tc.id || i}
                        toolCall={tc}
                        isLast={i === toolCalls.length - 1}
                        isStreaming={isStreaming}
                      />
                    ))}
                  </div>
                )}

                {/* "Hoàn tất" row at bottom when complete */}
                {isComplete && content && (
                  <div className="flex items-center gap-1.5 pt-1 text-text-tertiary">
                    <CheckCircle size={12} className="text-[var(--accent-green)]" />
                    <span className="text-[11px]">Hoàn tất</span>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}

/* ---- Custom Sparkle SVG (kept for backward compat imports) ---- */

export function SparkleIcon({ live }: { live: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      className={live ? "sparkle-live" : ""}
      style={live ? undefined : { opacity: 0.35 }}
    >
      {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
        <line
          key={angle}
          x1="8"
          y1="2"
          x2="8"
          y2="4.5"
          stroke="currentColor"
          strokeWidth="1.2"
          strokeLinecap="round"
          transform={`rotate(${angle} 8 8)`}
        />
      ))}
      <circle
        className={live ? "sparkle-center" : ""}
        cx="8"
        cy="8"
        r="1.2"
        fill="currentColor"
      />
    </svg>
  );
}

/* ---- Inline Tool Card ---- */

export function InlineToolCard({
  toolCall,
  isLast,
  isStreaming,
}: {
  toolCall: ToolCallInfo;
  isLast: boolean;
  isStreaming: boolean;
}) {
  const hasResult = !!toolCall.result;
  const isPending = isLast && isStreaming && !hasResult;

  const argsPreview = toolCall.args
    ? Object.entries(toolCall.args)
        .slice(0, 2)
        .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
        .join(", ")
    : "";

  return (
    <div>
      {/* Tool card row */}
      <div className="th-tool-card">
        {/* Gear icon */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          className={isPending ? "gear-spinning shrink-0" : "shrink-0"}
          style={{ color: "var(--accent-orange)" }}
        >
          <path
            d="M8 10a2 2 0 100-4 2 2 0 000 4z"
            stroke="currentColor"
            strokeWidth="1.2"
          />
          <path
            d="M6.9 1.7l-.3 1.2a4.6 4.6 0 00-1.5.9L4 3.4l-1.1 2 .9.9a4.5 4.5 0 000 1.8l-.9.9 1.1 2 1.1-.4a4.6 4.6 0 001.5.9l.3 1.2h2.2l.3-1.2a4.6 4.6 0 001.5-.9l1.1.4 1.1-2-.9-.9a4.5 4.5 0 000-1.8l.9-.9-1.1-2-1.1.4a4.6 4.6 0 00-1.5-.9l-.3-1.2H6.9z"
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinejoin="round"
          />
        </svg>

        {/* Function name */}
        <span className="th-tool-fn">{toolCall.name}</span>

        {/* Args preview */}
        {argsPreview && (
          <span className="th-tool-args">{argsPreview}</span>
        )}

        {/* Status: dots or checkmark */}
        <span className="ml-auto shrink-0">
          {isPending ? (
            <span className="flex gap-0.5">
              <span className="w-1 h-1 rounded-full bg-[var(--accent-orange)] animate-pulse-dot" style={{ animationDelay: "0s" }} />
              <span className="w-1 h-1 rounded-full bg-[var(--accent-orange)] animate-pulse-dot" style={{ animationDelay: "0.2s" }} />
              <span className="w-1 h-1 rounded-full bg-[var(--accent-orange)] animate-pulse-dot" style={{ animationDelay: "0.4s" }} />
            </span>
          ) : hasResult ? (
            <span className="flex items-center gap-1 text-[var(--accent-green)]">
              <Check size={12} />
              <span className="text-[10px] font-medium">hoàn thành</span>
            </span>
          ) : null}
        </span>
      </div>

      {/* Shimmer bar while loading */}
      {isPending && <div className="th-shimmer-bar" />}

      {/* Result box */}
      {hasResult && (
        <div className="th-tool-result">
          {truncateResult(toolCall.result!)}
        </div>
      )}

      {/* Sprint 146b: Post-tool processing indicator */}
      {hasResult && isLast && isStreaming && (
        <div className="flex items-center gap-1.5 ml-[26px] mt-1 text-text-tertiary">
          <span className="flex gap-0.5">
            <span className="w-1 h-1 rounded-full bg-[var(--accent-orange)] animate-pulse-dot" style={{ animationDelay: "0s" }} />
            <span className="w-1 h-1 rounded-full bg-[var(--accent-orange)] animate-pulse-dot" style={{ animationDelay: "0.2s" }} />
            <span className="w-1 h-1 rounded-full bg-[var(--accent-orange)] animate-pulse-dot" style={{ animationDelay: "0.4s" }} />
          </span>
          <span className="text-[10px]">Đang phân tích kết quả...</span>
        </div>
      )}
    </div>
  );
}

function truncateResult(result: string): string {
  if (result.length <= 300) return result;
  const cut = result.slice(0, 300);
  const sp = cut.lastIndexOf(" ");
  return (sp > 200 ? cut.slice(0, sp) : cut) + "...";
}
