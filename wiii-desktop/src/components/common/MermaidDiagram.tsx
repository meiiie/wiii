/**
 * MermaidDiagram — Renders Mermaid syntax as inline SVG.
 * Sprint 179: "Biểu Đồ Sống"
 *
 * Lazy-loads mermaid library (400KB+ WASM) on first render.
 * Supports dual-theme (light/dark) via Tailwind dark: class.
 */
import { useEffect, useRef, useState, memo } from "react";

let mermaidInstance: typeof import("mermaid") | null = null;

async function ensureMermaid(isDark: boolean): Promise<typeof import("mermaid")> {
  if (!mermaidInstance) {
    const mod = await import("mermaid");
    mermaidInstance = mod;
  }
  // Re-initialize theme on each render to handle dark mode switches
  mermaidInstance.default.initialize({
    startOnLoad: false,
    theme: isDark ? "dark" : "default",
    securityLevel: "strict",
    fontFamily: "'Inter', sans-serif",
  });
  return mermaidInstance;
}

interface MermaidDiagramProps {
  code: string;
  className?: string;
}

const MermaidDiagram = memo(function MermaidDiagram({ code, className = "" }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const idRef = useRef(`mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);

  // Detect dark mode from document class
  const isDark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");

  useEffect(() => {
    let cancelled = false;

    async function render() {
      if (!containerRef.current || !code.trim()) return;
      setLoading(true);
      setError(null);

      try {
        const mermaid = await ensureMermaid(isDark);
        if (cancelled) return;

        const { svg } = await mermaid.default.render(idRef.current, code.trim());
        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = svg;
        setLoading(false);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Không thể render biểu đồ");
        setLoading(false);
      }
    }

    render();
    return () => { cancelled = true; };
  }, [code, isDark]);

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 ${className}`}>
        <p className="text-sm text-red-600 dark:text-red-400 mb-2">Lỗi biểu đồ Mermaid</p>
        <pre className="text-xs text-red-500 dark:text-red-300 overflow-x-auto whitespace-pre-wrap">{code}</pre>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {loading && (
        <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
          <span className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-transparent rounded-full" />
          Đang vẽ biểu đồ...
        </div>
      )}
      <div
        ref={containerRef}
        className="mermaid-container overflow-x-auto [&>svg]:max-w-full [&>svg]:h-auto"
      />
    </div>
  );
});

export default MermaidDiagram;
