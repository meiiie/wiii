/**
 * SkillTree — displays Wiii's tracked skills with lifecycle indicators.
 * Sprint 170: "Linh Hồn Sống"
 */
import { motion } from "motion/react";
import type { LivingAgentSkill, SkillStatus } from "@/api/types";

interface SkillTreeProps {
  skills: LivingAgentSkill[];
}

const STATUS_CONFIG: Record<
  SkillStatus,
  { color: string; label: string; progress: number }
> = {
  discovered: { color: "#9ca3af", label: "Discovered", progress: 0.1 },
  learning: { color: "#6366f1", label: "Learning", progress: 0.3 },
  practicing: { color: "#3b82f6", label: "Practicing", progress: 0.55 },
  evaluating: { color: "#f59e0b", label: "Evaluating", progress: 0.75 },
  mastered: { color: "#10b981", label: "Mastered", progress: 1.0 },
  archived: { color: "#6b7280", label: "Archived", progress: 1.0 },
};

function SkillCard({ skill }: { skill: LivingAgentSkill }) {
  const config = STATUS_CONFIG[skill.status] || STATUS_CONFIG.discovered;

  return (
    <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-[var(--text-primary)] truncate">
          {skill.skill_name}
        </span>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
          style={{
            backgroundColor: `${config.color}20`,
            color: config.color,
          }}
        >
          {config.label}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-[var(--bg-tertiary)] rounded-full overflow-hidden mb-2">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: config.color }}
          initial={{ width: 0 }}
          animate={{ width: `${skill.confidence * 100}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>

      <div className="flex items-center justify-between text-[10px] text-[var(--text-tertiary)]">
        <span>{skill.domain}</span>
        <span>
          {skill.usage_count > 0
            ? `${skill.usage_count}x used`
            : "Not used yet"}
        </span>
      </div>
    </div>
  );
}

export function SkillTree({ skills }: SkillTreeProps) {
  if (skills.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-[var(--text-tertiary)]">
        Wiii chua hoc ky nang nao.
      </div>
    );
  }

  // Group by status
  const active = skills.filter(
    (s) => s.status !== "mastered" && s.status !== "archived"
  );
  const mastered = skills.filter((s) => s.status === "mastered");

  return (
    <div className="space-y-3">
      {active.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
            Dang hoc ({active.length})
          </div>
          <div className="space-y-2">
            {active.map((skill) => (
              <SkillCard key={skill.id} skill={skill} />
            ))}
          </div>
        </div>
      )}

      {mastered.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
            Da thong thao ({mastered.length})
          </div>
          <div className="space-y-2">
            {mastered.map((skill) => (
              <SkillCard key={skill.id} skill={skill} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
