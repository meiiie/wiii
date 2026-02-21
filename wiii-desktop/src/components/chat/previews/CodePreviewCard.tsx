/**
 * CodePreviewCard — Code block preview with syntax highlighting.
 * Sprint 166: Language badge, copy button, syntax highlight via MarkdownRenderer.
 */
import { useState } from "react";
import { Code, Copy, Check } from "lucide-react";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import type { PreviewItemData } from "@/api/types";

interface Props {
  item: PreviewItemData;
  onClick?: () => void;
}

export function CodePreviewCard({ item, onClick }: Props) {
  const [copied, setCopied] = useState(false);
  const language = (item.metadata?.language as string) ?? "";
  const code = item.snippet ?? "";

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  // Wrap code in markdown fenced block for MarkdownRenderer
  const markdownContent = `\`\`\`${language}\n${code}\n\`\`\``;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick?.();
      }}
      className="rounded-lg border border-[var(--border,#e5e5e0)] overflow-hidden
        bg-[var(--surface,#ffffff)] hover:bg-[var(--surface-hover,#fafaf5)]
        transition-colors text-left w-full group
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
      aria-label={`Code: ${item.title}`}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--surface-secondary,#f5f5f0)] border-b border-[var(--border,#e5e5e0)]">
        <div className="flex items-center gap-1.5">
          <Code size={14} className="text-[var(--text-tertiary,#999)]" />
          <h4 className="text-xs font-medium text-[var(--text-primary,#1a1a1a)] truncate">
            {item.title}
          </h4>
          {language && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--accent,#c2662d)]/10 text-[var(--accent,#c2662d)] font-medium uppercase tracking-wide flex-shrink-0">
              {language}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className="p-1 rounded hover:bg-[var(--surface-hover,#fafaf5)] transition-colors flex-shrink-0"
          aria-label={copied ? "Copied" : "Copy code"}
        >
          {copied ? (
            <Check size={14} className="text-green-500" />
          ) : (
            <Copy size={14} className="text-[var(--text-tertiary,#999)]" />
          )}
        </button>
      </div>

      {/* Code content — max 6 lines visible */}
      <div className="max-h-36 overflow-hidden text-xs">
        <MarkdownRenderer content={markdownContent} className="preview-code-block" />
      </div>
    </div>
  );
}
