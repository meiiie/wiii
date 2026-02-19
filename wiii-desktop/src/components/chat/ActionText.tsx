/**
 * ActionText — styled narrative text between thinking blocks.
 * Sprint 149: Replaces bare <p> with accent-bordered container + arrow icon.
 */
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";

interface ActionTextProps {
  content: string;
  node?: string;
}

export function ActionText({ content }: ActionTextProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="action-text-block"
    >
      <ArrowRight size={14} className="shrink-0 mt-0.5" style={{ color: "var(--accent-orange)" }} />
      <p className="text-sm font-semibold text-text-primary/85 leading-relaxed">
        {content}
      </p>
    </motion.div>
  );
}
