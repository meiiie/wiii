/**
 * JournalView — displays Wiii's daily journal entries.
 * Sprint 170: "Linh Hồn Sống"
 */
import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown } from "lucide-react";
import type { LivingAgentJournalEntry } from "@/api/types";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

interface JournalViewProps {
  entries: LivingAgentJournalEntry[];
}

function JournalCard({ entry }: { entry: LivingAgentJournalEntry }) {
  const [expanded, setExpanded] = useState(false);

  const dateStr = entry.entry_date
    ? new Date(entry.entry_date).toLocaleDateString("vi-VN", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

  return (
    <div className="rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)] overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-[var(--bg-tertiary)] transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)]10 flex items-center justify-center">
            <span className="text-sm">
              {entry.mood_summary === "curious"
                ? "?"
                : entry.mood_summary === "happy"
                  ? "^^"
                  : entry.mood_summary === "tired"
                    ? ".."
                    : "-"}
            </span>
          </div>
          <div>
            <div className="text-sm font-medium text-[var(--text-primary)]">
              {dateStr}
            </div>
            <div className="text-xs text-[var(--text-tertiary)]">
              {entry.mood_summary} | Energy: {Math.round(entry.energy_avg * 100)}
              %
            </div>
          </div>
        </div>
        <motion.div animate={{ rotate: expanded ? 180 : 0 }}>
          <ChevronDown className="w-4 h-4 text-[var(--text-tertiary)]" />
        </motion.div>
      </button>

      {/* Content — collapsible */}
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
              <MarkdownRenderer content={entry.content} />

              {entry.learnings.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-1">
                    Dieu da hoc:
                  </div>
                  <ul className="list-disc list-inside text-xs text-[var(--text-tertiary)] space-y-0.5">
                    {entry.learnings.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}

              {entry.goals_next.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-1">
                    Muc tieu ngay mai:
                  </div>
                  <ul className="list-disc list-inside text-xs text-[var(--text-tertiary)] space-y-0.5">
                    {entry.goals_next.map((g, i) => (
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

export function JournalView({ entries }: JournalViewProps) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-[var(--text-tertiary)]">
        Wiii chua viet nhat ky nao.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) => (
        <JournalCard key={entry.id} entry={entry} />
      ))}
    </div>
  );
}
