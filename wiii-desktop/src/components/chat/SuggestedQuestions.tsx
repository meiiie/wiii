import { motion } from "motion/react";
import { pillEntry, pillStagger } from "@/lib/animations";

interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

export function SuggestedQuestions({ questions, onSelect }: SuggestedQuestionsProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="text-[11px] text-text-tertiary mb-1.5 font-medium">Mình gợi ý:</p>
      <motion.div
        className="flex flex-wrap gap-1.5"
        variants={pillStagger}
        initial="hidden"
        animate="visible"
        role="group"
        aria-label="Câu hỏi gợi ý"
      >
      {questions.map((q, i) => (
        <motion.button
          key={i}
          variants={pillEntry}
          onClick={() => onSelect(q)}
          className="px-3 py-1.5 rounded-full bg-surface border border-border text-xs font-medium text-text-secondary hover:border-[var(--accent-orange)] hover:text-[var(--accent-orange)] transition-colors"
          whileHover={{ scale: 1.04, boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }}
          whileTap={{ scale: 0.97 }}
          aria-label={`Hỏi: ${q}`}
        >
          {q}
        </motion.button>
      ))}
      </motion.div>
    </div>
  );
}
