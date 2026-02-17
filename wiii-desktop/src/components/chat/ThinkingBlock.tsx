import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, Check } from "lucide-react";
import type { ToolCallInfo } from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

interface ThinkingBlockProps {
  content: string;
  isStreaming?: boolean;
  /** Duration in seconds — used for completed messages from history */
  savedDuration?: number;
  /** Tool calls to render inline inside the thinking block */
  toolCalls?: ToolCallInfo[];
  /** Custom label for the thinking header (e.g. "Phân tích câu hỏi") */
  label?: string;
}

/**
 * Claude-style thinking block with inline tool cards and markdown rendering.
 *
 * - Auto-expands during streaming
 * - Auto-collapses when streaming stops
 * - Shows "Đang suy nghĩ Xs" with live timer
 * - Shows "Đã suy nghĩ Xs" for completed messages
 * - Renders thinking content as rich markdown (not bullet list)
 * - Inline tool call cards (gear spin, orange mono fn name, status)
 * - Custom sparkle SVG (live vs done state)
 */
export function ThinkingBlock({
  content,
  isStreaming = false,
  savedDuration,
  toolCalls,
  label: customLabel,
}: ThinkingBlockProps) {
  const [expanded, setExpanded] = useState(isStreaming);
  const [duration, setDuration] = useState(savedDuration || 0);
  const startTimeRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
      // Streaming ended — freeze timer, auto-collapse
      if (timerRef.current) clearInterval(timerRef.current);
      setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
      startTimeRef.current = null;
      // Auto-collapse after a brief moment
      const collapseTimer = setTimeout(() => setExpanded(false), 500);
      return () => clearTimeout(collapseTimer);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isStreaming]);

  if (!content && (!toolCalls || toolCalls.length === 0)) return null;

  // Display label: custom label (from block) or default
  const baseLabel = customLabel || (isStreaming ? "Wiii đang suy nghĩ" : "Wiii đã suy nghĩ");
  const durationSuffix = duration > 0 ? ` · ${duration}s` : (isStreaming ? "..." : "");
  const durationLabel = baseLabel + durationSuffix;

  return (
    <motion.div
      className="mb-3"
      animate={isStreaming ? { opacity: [0.85, 1, 0.85] } : { opacity: 1 }}
      transition={isStreaming ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }}
    >
      {/* Trigger — "Thought for X seconds" */}
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="flex items-center gap-2 text-[13px] text-[var(--thinking-text)] hover:opacity-80 transition-opacity"
      >
        <SparkleIcon live={isStreaming} />
        <span className="font-medium">{durationLabel}</span>
        <ChevronDown
          size={14}
          className={`transition-transform duration-200 ${
            expanded ? "rotate-0" : "-rotate-90"
          }`}
        />
      </button>

      {/* Content — collapsible with AnimatePresence */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div
              className={`mt-2 rounded-lg border border-[var(--thinking-border)]/30 overflow-hidden ${
                isStreaming ? "thinking-shimmer" : "bg-[var(--thinking-bg)]"
              }`}
            >
              <div className="px-3 py-2.5">
                {/* Render thinking content as markdown */}
                {content && (
                  <div className="thinking-content text-xs text-[var(--thinking-text)] leading-relaxed">
                    <MarkdownRenderer content={content} />
                    {isStreaming && (!toolCalls || toolCalls.length === 0) && (
                      <span className="inline-block w-1.5 h-3.5 bg-[var(--thinking-text)] opacity-40 ml-0.5 animate-pulse rounded-sm" />
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
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ---- Custom Sparkle SVG ---- */

function SparkleIcon({ live }: { live: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      className={live ? "sparkle-live" : ""}
      style={live ? undefined : { opacity: 0.35 }}
    >
      {/* 8 rotating lines */}
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
      {/* Center dot */}
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

function InlineToolCard({
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
              <span className="text-[10px] font-medium">done</span>
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
    </div>
  );
}

function truncateResult(result: string): string {
  if (result.length <= 120) return result;
  return result.slice(0, 120) + "...";
}
