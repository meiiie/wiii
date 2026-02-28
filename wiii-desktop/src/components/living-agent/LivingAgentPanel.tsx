/**
 * LivingAgentPanel — main dashboard for Wiii's autonomous life.
 * Sprint 170: "Linh Hồn Sống"
 *
 * Displays mood, heartbeat, skills, and journal in a tabbed panel.
 * Can be embedded in Settings or shown as a standalone view.
 */
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Brain, BookOpen, Zap, Heart, RefreshCw, Target, Eye } from "lucide-react";
import { useLivingAgentStore } from "@/stores/living-agent-store";
import { MoodIndicator } from "./MoodIndicator";
import { SkillTree } from "./SkillTree";
import { JournalView } from "./JournalView";
import { HeartbeatStatus } from "./HeartbeatStatus";
import { GoalsView } from "./GoalsView";
import { ReflectionsView } from "./ReflectionsView";

type Tab = "overview" | "skills" | "goals" | "journal" | "reflections";

const TABS: { id: Tab; label: string; icon: typeof Brain }[] = [
  { id: "overview", label: "Tổng quan", icon: Heart },
  { id: "skills", label: "Kỹ năng", icon: Zap },
  { id: "goals", label: "Mục tiêu", icon: Target },
  { id: "journal", label: "Nhật ký", icon: BookOpen },
  { id: "reflections", label: "Suy ngẫm", icon: Eye },
];

export function LivingAgentPanel() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const {
    enabled,
    soulName,
    emotionalState,
    heartbeat,
    skills,
    goals,
    reflections,
    journalEntries,
    loading,
    fetchStatus,
    fetchEmotionalState,
    fetchSkills,
    fetchJournal,
    fetchGoals,
    fetchReflections,
  } = useLivingAgentStore();

  // Fetch on mount
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Auto-refresh emotional state every 30s while panel is open
  useEffect(() => {
    if (!enabled) return;
    const interval = setInterval(() => {
      fetchEmotionalState();
    }, 30_000);
    return () => clearInterval(interval);
  }, [enabled, fetchEmotionalState]);

  // Fetch tab-specific data
  useEffect(() => {
    if (!enabled) return;
    if (activeTab === "skills") fetchSkills();
    if (activeTab === "goals") fetchGoals();
    if (activeTab === "journal") fetchJournal();
    if (activeTab === "reflections") fetchReflections();
  }, [activeTab, enabled, fetchSkills, fetchGoals, fetchJournal, fetchReflections]);

  const handleRefresh = useCallback(() => {
    fetchStatus();
    if (activeTab === "skills") fetchSkills();
    if (activeTab === "goals") fetchGoals();
    if (activeTab === "journal") fetchJournal();
    if (activeTab === "reflections") fetchReflections();
  }, [activeTab, fetchStatus, fetchSkills, fetchGoals, fetchJournal, fetchReflections]);

  if (!enabled) {
    return (
      <div className="p-6 text-center">
        <Brain className="w-12 h-12 mx-auto mb-3 text-[var(--text-tertiary)]" />
        <div className="text-sm text-[var(--text-secondary)] mb-1">
          Tính năng này sẽ sớm ra mắt
        </div>
        <div className="text-xs text-[var(--text-tertiary)]">
          Wiii đang hoàn thiện khả năng tự học và phát triển. Hãy quay lại sau nhé!
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-primary)]">
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Brain className="w-5 h-5 text-[var(--accent)]" />
          </motion.div>
          <div>
            <div className="text-sm font-medium text-[var(--text-primary)]">
              {soulName || "Wiii"} — Linh Hồn Sống
            </div>
            {emotionalState && (
              <MoodIndicator state={emotionalState} compact />
            )}
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="p-1.5 rounded-md hover:bg-[var(--bg-tertiary)] transition-colors"
          title="Làm mới"
        >
          <RefreshCw
            className={`w-4 h-4 text-[var(--text-tertiary)] ${loading ? "animate-spin" : ""}`}
          />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[var(--border-primary)]">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors
                ${
                  isActive
                    ? "text-[var(--accent)] border-b-2 border-[var(--accent)]"
                    : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
                }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <AnimatePresence mode="wait">
          {activeTab === "overview" && (
            <motion.div
              key="overview"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              {/* Emotional state */}
              {emotionalState && (
                <div>
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
                    Cảm xúc
                  </div>
                  <MoodIndicator state={emotionalState} />
                </div>
              )}

              {/* Heartbeat */}
              {heartbeat && (
                <div>
                  <div className="text-xs font-medium text-[var(--text-secondary)] mb-2 uppercase tracking-wider">
                    Nhịp tim
                  </div>
                  <HeartbeatStatus heartbeat={heartbeat} />
                </div>
              )}
            </motion.div>
          )}

          {activeTab === "skills" && (
            <motion.div
              key="skills"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <SkillTree skills={skills} />
            </motion.div>
          )}

          {activeTab === "goals" && (
            <motion.div
              key="goals"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <GoalsView goals={goals} />
            </motion.div>
          )}

          {activeTab === "journal" && (
            <motion.div
              key="journal"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <JournalView entries={journalEntries} />
            </motion.div>
          )}

          {activeTab === "reflections" && (
            <motion.div
              key="reflections"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <ReflectionsView reflections={reflections} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
