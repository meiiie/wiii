/**
 * SubagentGroup — visual container for parallel dispatch + aggregation.
 * Sprint 164: Shows worker lanes with nested ThinkingBlocks + AggregationCard.
 */
import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, GitBranch, CheckCircle, Loader2 } from "lucide-react";
import type {
  SubagentGroupBlockData,
  ThinkingBlockData,
  AggregationSummary,
  ThinkingLevel,
} from "@/api/types";
import { ThinkingBlock } from "./ThinkingBlock";

const AGENT_LABELS: Record<string, string> = {
  rag: "Tra cứu tri thức",
  rag_agent: "Tra cứu tri thức",
  tutor: "Soạn bài giảng",
  tutor_agent: "Soạn bài giảng",
  search: "Tìm kiếm sản phẩm",
  product_search_agent: "Tìm kiếm sản phẩm",
  direct: "Trả lời trực tiếp",
  memory: "Trí nhớ",
  memory_agent: "Trí nhớ",
};

function getAgentLabel(name: string): string {
  return AGENT_LABELS[name] || name;
}

interface SubagentGroupProps {
  group: SubagentGroupBlockData;
  childBlocks: ThinkingBlockData[];
  isStreaming: boolean;
  thinkingLevel: ThinkingLevel;
}

export function SubagentGroup({
  group,
  childBlocks,
  isStreaming,
  thinkingLevel,
}: SubagentGroupProps) {
  // minimal → hidden
  if (thinkingLevel === "minimal") return null;

  const isComplete = !!group.endTime;
  const [expanded, setExpanded] = useState(
    thinkingLevel === "detailed" ? true : !isComplete,
  );

  const elapsed = group.endTime
    ? ((group.endTime - group.startTime) / 1000).toFixed(1)
    : null;

  return (
    <div className="my-2 rounded-lg border border-border/60 bg-surface-secondary/30 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-tertiary/40 transition-colors"
      >
        <GitBranch size={14} className="text-[var(--accent-orange)] shrink-0" />
        <span className="text-xs font-medium text-text-secondary flex-1 truncate">
          {group.label}
          <span className="ml-1.5 text-text-tertiary font-normal">
            — {group.workers.length} agents
          </span>
        </span>
        {elapsed && (
          <span className="text-[10px] text-text-tertiary tabular-nums">{elapsed}s</span>
        )}
        {isComplete ? (
          <CheckCircle size={12} className="text-green-500 shrink-0" />
        ) : (
          <Loader2 size={12} className="text-[var(--accent-orange)] animate-spin shrink-0" />
        )}
        <ChevronDown
          size={14}
          className={`text-text-tertiary transition-transform shrink-0 ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {/* Expanded content */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-2.5 space-y-1.5">
              {/* Worker lanes */}
              {group.workers.map((worker) => {
                const workerBlocks = childBlocks.filter(
                  (b) => b.workerNode === worker.agentName,
                );
                const workerElapsed =
                  worker.endTime && worker.startTime
                    ? ((worker.endTime - worker.startTime) / 1000).toFixed(1)
                    : null;

                return (
                  <div key={worker.agentName} className="pl-2 border-l-2 border-border/50">
                    {/* Worker header */}
                    <div className="flex items-center gap-1.5 py-1">
                      {worker.status === "completed" ? (
                        <CheckCircle size={10} className="text-green-500 shrink-0" />
                      ) : worker.status === "error" ? (
                        <span className="w-2.5 h-2.5 rounded-full bg-red-400 shrink-0" />
                      ) : (
                        <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
                      )}
                      <span className="text-[11px] font-medium text-text-secondary">
                        {getAgentLabel(worker.agentName)}
                      </span>
                      {workerElapsed && (
                        <span className="text-[10px] text-text-tertiary tabular-nums ml-auto">
                          {workerElapsed}s
                        </span>
                      )}
                    </div>

                    {/* Per-worker status messages */}
                    {worker.statusMessages.length > 0 && (
                      <div className="ml-4 space-y-0.5 mb-1">
                        {worker.statusMessages.map((msg, idx) => (
                          <div key={idx} className="flex items-center gap-1 text-[10px] text-text-tertiary">
                            <span className="w-1 h-1 rounded-full bg-text-tertiary/50 shrink-0" />
                            <span>{msg}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Nested thinking blocks for this worker */}
                    {workerBlocks.map((tb) => (
                      <div key={tb.id} className="ml-2">
                        <ThinkingBlock
                          content={tb.content}
                          toolCalls={tb.toolCalls}
                          label={tb.label}
                          summary={tb.summary || tb.label}
                          isStreaming={!tb.endTime && isStreaming}
                          savedDuration={
                            tb.startTime && tb.endTime
                              ? Math.round((tb.endTime - tb.startTime) / 1000)
                              : undefined
                          }
                          thinkingLevel={thinkingLevel}
                        />
                      </div>
                    ))}
                  </div>
                );
              })}

              {/* Aggregation card */}
              {group.aggregation && (
                <AggregationCard aggregation={group.aggregation} />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AggregationCard({ aggregation }: { aggregation: AggregationSummary }) {
  const strategyLabels: Record<string, string> = {
    synthesize: "Tổng hợp",
    use_best: "Dùng kết quả tốt nhất",
    re_route: "Gửi lại",
    escalate: "Báo lỗi",
  };

  const confidencePct = Math.round(aggregation.confidence * 100);

  return (
    <div className="mt-1 px-2.5 py-2 rounded-md bg-surface-tertiary/50 border border-border/40">
      <div className="flex items-center gap-2 text-[11px]">
        <span className="font-medium text-text-secondary">
          Chiến lược: {strategyLabels[aggregation.strategy] || aggregation.strategy}
        </span>
        {aggregation.primaryAgent && (
          <span className="text-text-tertiary">
            | {getAgentLabel(aggregation.primaryAgent)} (chính)
          </span>
        )}
      </div>
      {/* Confidence bar */}
      <div className="mt-1.5 flex items-center gap-2">
        <div className="flex-1 h-1.5 rounded-full bg-border/40 overflow-hidden">
          <div
            className="h-full rounded-full bg-[var(--accent-orange)] transition-all"
            style={{ width: `${confidencePct}%` }}
          />
        </div>
        <span className="text-[10px] text-text-tertiary tabular-nums w-8 text-right">
          {confidencePct}%
        </span>
      </div>
      {aggregation.reasoning && (
        <p className="mt-1 text-[10px] text-text-tertiary leading-relaxed line-clamp-2">
          {aggregation.reasoning}
        </p>
      )}
    </div>
  );
}
