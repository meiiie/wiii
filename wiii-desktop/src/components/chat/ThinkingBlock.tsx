import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, Check, Copy, Clock, CheckCircle, Search, Globe, BookOpen, Wrench } from "lucide-react";
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
      // Sprint 165: Dynamic collapse delay based on content length
      // Short content collapses quickly, long content stays visible longer
      if (thinkingLevel !== "detailed") {
        const contentLen = content?.length ?? 0;
        const collapseDelay = Math.min(Math.max(1500, contentLen * 5), 5000);
        const collapseTimer = setTimeout(() => setExpanded(false), collapseDelay);
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
    <div className={`mb-1.5 group/thinking ${isStreaming ? "th-streaming-border" : ""}`}>
      {/* Header row — Claude-style collapsed/expanded toggle */}
      <div className="flex items-center">
        {hasContent ? (
          <button
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            className="flex items-center gap-1.5 text-[13px] text-text-tertiary hover:text-text-secondary transition-colors"
          >
            {/* Sprint 147: Animated indicator — pulsing ring during streaming, scale-pop checkmark on complete */}
            {isComplete ? (
              <motion.span
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 400, damping: 15 }}
              >
                <CheckCircle size={14} className="text-[var(--accent-green)] shrink-0" />
              </motion.span>
            ) : (
              <span className="relative shrink-0 flex items-center justify-center w-[14px] h-[14px]">
                <span className="absolute inset-0 rounded-full border border-[var(--accent-orange)] animate-ping opacity-30" />
                <Clock size={12} className="relative text-[var(--accent-orange)]" />
              </span>
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
                  <div className="text-xs text-text-secondary leading-relaxed thinking-markdown">
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

/* ---- Tool Icon mapping ---- */

function ToolIcon({ name, spinning }: { name: string; spinning?: boolean }) {
  const cls = `shrink-0 ${spinning ? "animate-spin" : ""}`;
  const color = "var(--accent-orange)";

  if (name === "tool_knowledge_search" || name === "tool_maritime_search") {
    return <BookOpen size={14} className={cls} style={{ color }} />;
  }
  if (name === "tool_web_search" || name === "tool_search_news" || name === "tool_search_legal" || name === "tool_search_maritime") {
    return <Globe size={14} className={cls} style={{ color }} />;
  }
  if (name === "tool_think") {
    return <Search size={14} className={cls} style={{ color }} />;
  }
  // Generic tool icon (gear SVG)
  return (
    <Wrench size={14} className={cls} style={{ color }} />
  );
}

/* ---- Parse rich result metadata ---- */

interface ParsedToolResult {
  title?: string;
  domain?: string;
  score?: number;
  snippet: string;
}

function parseToolResult(name: string, result: string): ParsedToolResult {
  // Try to extract structured data for knowledge_search results
  if (name === "tool_knowledge_search" || name === "tool_maritime_search") {
    // Try JSON parse first
    try {
      const parsed = JSON.parse(result);
      if (parsed.title || parsed.document_title) {
        return {
          title: parsed.title || parsed.document_title,
          domain: parsed.domain_id || parsed.domain,
          score: parsed.score || parsed.relevance_score,
          snippet: parsed.content || parsed.snippet || truncateResult(result),
        };
      }
    } catch {
      // Not JSON — fall through to text extraction
    }
    // Try to extract title from text (e.g., "Title: COLREGs Rule 13\nContent: ...")
    const titleMatch = result.match(/(?:Title|Tiêu đề|Document):\s*(.+?)(?:\n|$)/i);
    if (titleMatch) {
      return {
        title: titleMatch[1].trim(),
        snippet: truncateResult(result.replace(titleMatch[0], "").trim()),
      };
    }
  }
  return { snippet: truncateResult(result) };
}

/* ---- Inline Tool Card — Sprint 147: Rich result cards ---- */

export function InlineToolCard({
  toolCall,
  isLast,
  isStreaming,
}: {
  toolCall: ToolCallInfo;
  isLast: boolean;
  isStreaming: boolean;
}) {
  const [resultExpanded, setResultExpanded] = useState(false);
  const hasResult = !!toolCall.result;
  const isPending = isLast && isStreaming && !hasResult;

  const argsPreview = toolCall.args
    ? Object.entries(toolCall.args)
        .slice(0, 2)
        .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
        .join(", ")
    : "";

  // Sprint 147: Parse structured result for rich display
  const parsed = hasResult ? parseToolResult(toolCall.name, toolCall.result!) : null;
  const isRichResult = parsed && parsed.title;

  // Sprint 147: Friendly tool name labels
  const toolLabel = _TOOL_LABELS[toolCall.name] || toolCall.name;

  return (
    <div>
      {/* Tool card row */}
      <div className="th-tool-card">
        {/* Sprint 147: Contextual tool icon */}
        <ToolIcon name={toolCall.name} spinning={isPending} />

        {/* Function name — friendly label */}
        <span className="th-tool-fn">{toolLabel}</span>

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
            <motion.span
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="flex items-center gap-1 text-[var(--accent-green)]"
            >
              <Check size={12} />
            </motion.span>
          ) : null}
        </span>
      </div>

      {/* Shimmer bar while loading */}
      {isPending && <div className="th-shimmer-bar" />}

      {/* Sprint 147: Rich result card for knowledge search */}
      {hasResult && isRichResult && (
        <button
          onClick={() => setResultExpanded(!resultExpanded)}
          className="th-tool-result-rich"
        >
          <div className="flex items-start gap-2">
            <BookOpen size={12} className="mt-0.5 shrink-0 text-[var(--accent-orange)]" />
            <div className="min-w-0 text-left">
              <div className="text-[11px] font-medium text-text-primary truncate">
                {parsed.title}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                {parsed.domain && (
                  <span className="th-tool-domain-tag">{parsed.domain}</span>
                )}
                {parsed.score != null && (
                  <span className="text-[9px] text-text-tertiary tabular-nums">
                    {(parsed.score * 100).toFixed(0)}% relevance
                  </span>
                )}
              </div>
              {resultExpanded && (
                <div className="mt-1.5 text-[10px] text-text-secondary leading-relaxed">
                  {parsed.snippet}
                </div>
              )}
            </div>
            <ChevronDown size={10} className={`shrink-0 mt-1 text-text-tertiary transition-transform ${resultExpanded ? "rotate-0" : "-rotate-90"}`} />
          </div>
        </button>
      )}

      {/* Standard result box for non-rich tools */}
      {hasResult && !isRichResult && (
        <div className="th-tool-result">
          {parsed?.snippet || truncateResult(toolCall.result!)}
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

/* ---- Friendly tool name labels ---- */

const _TOOL_LABELS: Record<string, string> = {
  tool_knowledge_search: "Tra cứu kiến thức",
  tool_maritime_search: "Tra cứu hàng hải",
  tool_web_search: "Tìm kiếm web",
  tool_search_news: "Tìm tin tức",
  tool_search_legal: "Tra cứu pháp luật",
  tool_search_maritime: "Tìm kiếm hàng hải",
  tool_current_datetime: "Thời gian hiện tại",
  tool_calculator: "Máy tính",
  tool_think: "Suy nghĩ",
  tool_save_user_info: "Lưu thông tin",
  tool_get_user_info: "Truy xuất thông tin",
};

function truncateResult(result: string): string {
  if (result.length <= 300) return result;
  const cut = result.slice(0, 300);
  const sp = cut.lastIndexOf(" ");
  return (sp > 200 ? cut.slice(0, sp) : cut) + "...";
}
