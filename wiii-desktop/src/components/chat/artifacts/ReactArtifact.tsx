/**
 * ReactArtifact — Sandpack live preview for React/JS code.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * Lazy-loads @codesandbox/sandpack-react (~400 KB gzip) on first use.
 * Falls back to HTML iframe if Sandpack fails to load.
 */
import { lazy, Suspense, useState } from "react";
import { createSandpackConfig } from "@/lib/sandpack-runtime";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";
import type { ArtifactData } from "@/api/types";

interface Props {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

// Lazy-load Sandpack components
const SandpackPreviewWrapper = lazy(async () => {
  try {
    const mod = await import("@codesandbox/sandpack-react");
    return {
      default: function SandpackWrapper({ code, language }: { code: string; language: string }) {
        const config = createSandpackConfig(code, language);
        return (
          <mod.SandpackProvider
            template={config.template}
            files={config.files}
            theme="auto"
          >
            <mod.SandpackLayout>
              <mod.SandpackCodeEditor style={{ height: "300px" }} />
              <mod.SandpackPreview style={{ height: "300px" }} />
            </mod.SandpackLayout>
          </mod.SandpackProvider>
        );
      },
    };
  } catch {
    // Fallback if Sandpack not installed
    return {
      default: function FallbackWrapper({ code, language }: { code: string; language: string }) {
        const codeBlock = `\`\`\`${language}\n${code}\n\`\`\``;
        return (
          <div className="p-3">
            <div className="text-xs text-text-tertiary mb-2">
              Sandpack chưa được cài đặt. Hiển thị code thay thế.
            </div>
            <MarkdownRenderer content={codeBlock} />
          </div>
        );
      },
    };
  }
});

export default function ReactArtifact({ artifact, mode }: Props) {
  const [showPreview, setShowPreview] = useState(mode === "panel");
  const language = artifact.language || "jsx";

  if (mode === "card") {
    const codeBlock = `\`\`\`${language}\n${artifact.content}\n\`\`\``;
    return (
      <div className="text-sm">
        <MarkdownRenderer content={codeBlock} />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2 px-4 pt-2">
        <button
          onClick={() => setShowPreview(false)}
          className={`text-xs px-2 py-1 rounded ${!showPreview ? "bg-[var(--accent)] text-white" : "bg-surface-tertiary text-text-secondary"}`}
        >
          Code
        </button>
        <button
          onClick={() => setShowPreview(true)}
          className={`text-xs px-2 py-1 rounded ${showPreview ? "bg-[var(--accent)] text-white" : "bg-surface-tertiary text-text-secondary"}`}
        >
          Preview
        </button>
      </div>

      {showPreview ? (
        <Suspense
          fallback={
            <div className="flex items-center justify-center p-8 text-text-tertiary text-sm">
              <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mr-2" />
              Đang tải Sandpack...
            </div>
          }
        >
          <SandpackPreviewWrapper code={artifact.content} language={language} />
        </Suspense>
      ) : (
        <div className="px-4 text-sm">
          <MarkdownRenderer content={`\`\`\`${language}\n${artifact.content}\n\`\`\``} />
        </div>
      )}
    </div>
  );
}
