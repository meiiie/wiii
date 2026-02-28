/**
 * GoalsView — displays Wiii's goals with progress tracking.
 * Sprint 210: "Sống Thật"
 */
import { motion } from "motion/react";
import { Target, CheckCircle2, Clock, Sparkles } from "lucide-react";
import type { LivingAgentGoal } from "@/api/types";

interface GoalsViewProps {
  goals: LivingAgentGoal[];
}

const PRIORITY_CONFIG: Record<string, { color: string; label: string }> = {
  high: { color: "#ef4444", label: "Cao" },
  medium: { color: "#f59e0b", label: "Trung bình" },
  low: { color: "#6b7280", label: "Thấp" },
};

const STATUS_ICON: Record<string, typeof Target> = {
  proposed: Clock,
  active: Target,
  completed: CheckCircle2,
};

function GoalCard({ goal }: { goal: LivingAgentGoal }) {
  const priority = PRIORITY_CONFIG[goal.priority] || PRIORITY_CONFIG.medium;
  const Icon = STATUS_ICON[goal.status] || Target;
  const isCompleted = goal.status === "completed";

  return (
    <div
      className={`p-3 rounded-lg border transition-colors ${
        isCompleted
          ? "bg-[var(--bg-tertiary)] border-[var(--border-primary)] opacity-70"
          : "bg-[var(--bg-secondary)] border-[var(--border-primary)]"
      }`}
    >
      <div className="flex items-start gap-2.5 mb-2">
        <Icon
          className="w-4 h-4 mt-0.5 shrink-0"
          style={{ color: isCompleted ? "#10b981" : priority.color }}
        />
        <div className="flex-1 min-w-0">
          <div
            className={`text-sm font-medium ${
              isCompleted
                ? "text-[var(--text-tertiary)] line-through"
                : "text-[var(--text-primary)]"
            }`}
          >
            {goal.title}
          </div>
          {goal.description && (
            <div className="text-xs text-[var(--text-tertiary)] mt-0.5 line-clamp-2">
              {goal.description}
            </div>
          )}
        </div>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0"
          style={{
            backgroundColor: `${priority.color}20`,
            color: priority.color,
          }}
        >
          {priority.label}
        </span>
      </div>

      {/* Progress bar */}
      {!isCompleted && (
        <div className="mb-2">
          <div className="flex items-center justify-between text-[10px] text-[var(--text-tertiary)] mb-1">
            <span>Tiến độ</span>
            <span>{Math.round(goal.progress * 100)}%</span>
          </div>
          <div className="h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{ backgroundColor: "var(--accent)" }}
              initial={{ width: 0 }}
              animate={{ width: `${goal.progress * 100}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      )}

      {/* Milestones */}
      {goal.milestones.length > 0 && (
        <div className="space-y-0.5">
          {goal.milestones.map((milestone, i) => {
            const done = goal.completed_milestones.includes(milestone);
            return (
              <div
                key={i}
                className="flex items-center gap-1.5 text-[10px]"
              >
                <div
                  className={`w-2.5 h-2.5 rounded-full border ${
                    done
                      ? "bg-[#10b981] border-[#10b981]"
                      : "border-[var(--border-primary)]"
                  }`}
                />
                <span
                  className={
                    done
                      ? "text-[var(--text-tertiary)] line-through"
                      : "text-[var(--text-secondary)]"
                  }
                >
                  {milestone}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Source */}
      <div className="flex items-center gap-1 mt-2 text-[10px] text-[var(--text-tertiary)]">
        <Sparkles className="w-2.5 h-2.5" />
        <span>{goal.source === "soul" ? "Từ tâm hồn" : goal.source === "reflection" ? "Từ suy ngẫm" : goal.source}</span>
      </div>
    </div>
  );
}

export function GoalsView({ goals }: GoalsViewProps) {
  if (goals.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-[var(--text-tertiary)]">
        Wiii chưa có mục tiêu nào.
      </div>
    );
  }

  const active = goals.filter(
    (g) => g.status === "active" || g.status === "proposed"
  );
  const completed = goals.filter((g) => g.status === "completed");

  return (
    <div className="space-y-3">
      {active.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
            Đang theo đuổi ({active.length})
          </div>
          <div className="space-y-2">
            {active.map((goal) => (
              <GoalCard key={goal.id} goal={goal} />
            ))}
          </div>
        </div>
      )}

      {completed.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
            Đã hoàn thành ({completed.length})
          </div>
          <div className="space-y-2">
            {completed.map((goal) => (
              <GoalCard key={goal.id} goal={goal} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
