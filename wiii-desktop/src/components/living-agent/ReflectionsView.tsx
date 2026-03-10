/**
 * ReflectionsView — displays Wiii's daily self-reflections.
 * Sprint 210: "Sống Thật"
 */
import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, Lightbulb, TrendingUp, Eye } from "lucide-react";
import type { LivingAgentReflection } from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

interface ReflectionsViewProps {
  reflections: LivingAgentReflection[];
}

function ReflectionCard({
  reflection,
}: {
  reflection: LivingAgentReflection;
}) {
  const [expanded, setExpanded] = useState(false);

  const dateStr = reflection.reflection_date
    ? new Date(reflection.reflection_date).toLocaleDateString("vi-VN", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

  return (
    <div className="rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="w-full flex items-center justify-between p-3 hover:bg-[var(--bg-tertiary)] transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#06b6d420] flex items-center justify-center">
            <Eye className="w-4 h-4 text-[#06b6d4]" />
          </div>
          <div>
            <div className="text-sm font-medium text-[var(--text-primary)]">
              {dateStr}
            </div>
            <div className="text-xs text-[var(--text-tertiary)]">
              {reflection.insights.length > 0
                ? `${reflection.insights.length} nhận thức mới`
                : "Suy ngẫm"}
              {reflection.emotion_trend && ` · ${reflection.emotion_trend}`}
            </div>
          </div>
        </div>
        <motion.div animate={{ rotate: expanded ? 180 : 0 }}>
          <ChevronDown className="w-4 h-4 text-[var(--text-tertiary)]" />
        </motion.div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-[var(--border-primary)]"
          >
            <div className="p-3 text-sm">
              <MarkdownRenderer content={reflection.content} />

              {reflection.insights.length > 0 && (
                <div className="mt-3">
                  <div className="flex items-center gap-1 text-xs font-medium text-[var(--text-secondary)] mb-1">
                    <Lightbulb className="w-3 h-3" />
                    Nhận thức mới:
                  </div>
                  <ul className="list-disc list-inside text-xs text-[var(--text-tertiary)] space-y-0.5">
                    {reflection.insights.map((insight, i) => (
                      <li key={i}>{insight}</li>
                    ))}
                  </ul>
                </div>
              )}

              {reflection.patterns_noticed.length > 0 && (
                <div className="mt-2">
                  <div className="flex items-center gap-1 text-xs font-medium text-[var(--text-secondary)] mb-1">
                    <TrendingUp className="w-3 h-3" />
                    Xu hướng nhận ra:
                  </div>
                  <ul className="list-disc list-inside text-xs text-[var(--text-tertiary)] space-y-0.5">
                    {reflection.patterns_noticed.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {reflection.goals_next_week.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-1">
                    Mục tiêu sắp tới:
                  </div>
                  <ul className="list-disc list-inside text-xs text-[var(--text-tertiary)] space-y-0.5">
                    {reflection.goals_next_week.map((g, i) => (
                      <li key={i}>{g}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ReflectionsView({ reflections }: ReflectionsViewProps) {
  if (reflections.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-[var(--text-tertiary)]">
        Wiii chưa có suy ngẫm nào.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {reflections.map((r) => (
        <ReflectionCard key={r.id} reflection={r} />
      ))}
    </div>
  );
}
