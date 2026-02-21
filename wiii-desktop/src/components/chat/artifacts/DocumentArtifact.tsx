/**
 * DocumentArtifact — renders Markdown/text documents.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * For Markdown content: uses MarkdownRenderer.
 * For DOCX: would lazy-load docx-preview (not included in base).
 */
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

export default function DocumentArtifact({ artifact, mode }: Props) {
  const language = artifact.language?.toLowerCase() || "";
  const isMarkdown = language === "markdown" || language === "md" || !language;

  if (mode === "card") {
    // Show first ~200 chars as preview
    const preview = artifact.content.slice(0, 200) + (artifact.content.length > 200 ? "..." : "");
    return (
      <div className="text-sm p-2">
        <MarkdownRenderer content={preview} />
      </div>
    );
  }

  if (isMarkdown) {
    return (
      <div className="p-4 prose prose-sm dark:prose-invert max-w-none">
        <MarkdownRenderer content={artifact.content} />
      </div>
    );
  }

  // Fallback: plain text
  return (
    <div className="p-4">
      <pre className="text-sm font-mono text-text-secondary whitespace-pre-wrap leading-relaxed">
        {artifact.content}
      </pre>
    </div>
  );
}
