/**
 * ActionText - a light bridge between reasoning steps.
 *
 * It should never overpower either the thinking rail or the final answer.
 */
import { ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import { NODE_LABELS } from "@/lib/reasoning-labels";

interface ActionTextProps {
  content: string;
  node?: string;
}

function normalizeNode(node?: string) {
  return (node || "").toLowerCase().replace(/\s+/g, "_");
}

export function ActionText({ content, node }: ActionTextProps) {
  const label = NODE_LABELS[normalizeNode(node)] || "Chuyen buoc";

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="action-text-block"
    >
      <div className="action-text-block__rail" aria-hidden="true">
        <ArrowRight
          size={12}
          className="action-text-block__icon shrink-0"
          style={{ color: "var(--accent-orange)" }}
        />
      </div>

      <div className="action-text-block__body">
        <div className="action-text-block__label">
          <span className="action-text-block__label-dot" aria-hidden="true" />
          <span>{label}</span>
        </div>
        <p className="action-text-block__text">
          {content}
        </p>
      </div>
    </motion.div>
  );
}
