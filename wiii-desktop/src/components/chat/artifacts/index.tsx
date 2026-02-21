/**
 * Artifact Renderer Registry — dispatches on artifact_type.
 * Sprint 167: "Không Gian Sáng Tạo"
 * Sprint 167b: H-2 — ErrorBoundary around lazy renderers
 *
 * Plugin pattern: each artifact type has its own renderer component.
 * All renderers are lazy-loaded for zero base impact.
 */
import { lazy, Suspense } from "react";
import type { ArtifactData } from "@/api/types";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";

// Lazy-load renderers (code-split per type)
const CodeArtifact = lazy(() => import("./CodeArtifact"));
const HtmlArtifact = lazy(() => import("./HtmlArtifact"));
const ReactArtifact = lazy(() => import("./ReactArtifact"));
const TableArtifact = lazy(() => import("./TableArtifact"));
const ChartArtifact = lazy(() => import("./ChartArtifact"));
const ExcelArtifact = lazy(() => import("./ExcelArtifact"));
const DocumentArtifact = lazy(() => import("./DocumentArtifact"));

const LoadingFallback = (
  <div className="flex items-center justify-center p-8 text-text-tertiary text-sm">
    <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin mr-2" />
    Đang tải...
  </div>
);

interface ArtifactRendererProps {
  artifact: ArtifactData;
  mode: "card" | "panel";
}

export function ArtifactRenderer({ artifact, mode }: ArtifactRendererProps) {
  return (
    <ErrorBoundary>
      <Suspense fallback={LoadingFallback}>
        {renderByType(artifact, mode)}
      </Suspense>
    </ErrorBoundary>
  );
}

function renderByType(artifact: ArtifactData, mode: "card" | "panel") {
  switch (artifact.artifact_type) {
    case "code":
      return <CodeArtifact artifact={artifact} mode={mode} />;
    case "html":
      return <HtmlArtifact artifact={artifact} mode={mode} />;
    case "react":
      return <ReactArtifact artifact={artifact} mode={mode} />;
    case "table":
      return <TableArtifact artifact={artifact} mode={mode} />;
    case "chart":
      return <ChartArtifact artifact={artifact} mode={mode} />;
    case "excel":
      return <ExcelArtifact artifact={artifact} mode={mode} />;
    case "document":
      return <DocumentArtifact artifact={artifact} mode={mode} />;
    default:
      // Fallback to code display
      return <CodeArtifact artifact={artifact} mode={mode} />;
  }
}
