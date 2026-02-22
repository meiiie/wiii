/**
 * CodeEditor — lazy-loaded Monaco editor wrapper.
 * Sprint 167: "Không Gian Sáng Tạo"
 *
 * Uses @monaco-editor/react (~300 KB gzip), loaded on first code edit.
 * Read-only by default, editable when user clicks "Chỉnh sửa".
 * Theme matches Wiii dark/light mode.
 */
import { lazy, Suspense, useState, useCallback } from "react";
import { Pencil, Eye } from "lucide-react";
import { useSettingsStore } from "@/stores/settings-store";

// Lazy-load Monaco
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const MonacoEditor = lazy(async (): Promise<{ default: React.ComponentType<any> }> => {
  try {
    const mod = await import("@monaco-editor/react");
    return { default: mod.default };
  } catch {
    // Fallback if @monaco-editor/react not installed
    return {
      default: function FallbackEditor({ value }: { value: string }) {
        return (
          <pre className="p-4 text-xs font-mono text-text-secondary overflow-auto bg-surface-secondary rounded-lg max-h-[500px]">
            {value}
          </pre>
        );
      },
    };
  }
});

interface CodeEditorProps {
  code: string;
  language?: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
}

export function CodeEditor({
  code,
  language = "javascript",
  onChange,
  readOnly: defaultReadOnly = true,
  height = "400px",
}: CodeEditorProps) {
  const [readOnly, setReadOnly] = useState(defaultReadOnly);

  const toggleEdit = useCallback(() => {
    setReadOnly((r) => !r);
  }, []);

  // Map language names to Monaco IDs
  const monacoLang = (() => {
    const map: Record<string, string> = {
      python: "python",
      py: "python",
      python3: "python",
      javascript: "javascript",
      js: "javascript",
      typescript: "typescript",
      ts: "typescript",
      jsx: "javascript",
      tsx: "typescript",
      html: "html",
      css: "css",
      json: "json",
      sql: "sql",
      rust: "rust",
      go: "go",
      java: "java",
      cpp: "cpp",
      c: "c",
      bash: "shell",
      sh: "shell",
      yaml: "yaml",
      yml: "yaml",
      markdown: "markdown",
      md: "markdown",
    };
    return map[language.toLowerCase()] || language;
  })();

  // L-2: Read theme from settings store instead of DOM
  const theme = useSettingsStore((s) => s.settings.theme);
  const isDark = theme === "dark" || (theme === "system" && typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  return (
    <div className="relative">
      {/* Toggle edit button */}
      <div className="absolute top-2 right-2 z-10">
        <button
          onClick={toggleEdit}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-surface-tertiary/80 backdrop-blur hover:bg-border text-text-secondary transition-colors"
          title={readOnly ? "Chỉnh sửa" : "Chỉ xem"}
        >
          {readOnly ? <Pencil size={12} /> : <Eye size={12} />}
          {readOnly ? "Chỉnh sửa" : "Chỉ xem"}
        </button>
      </div>

      <Suspense
        fallback={
          <pre className="p-4 text-xs font-mono text-text-secondary overflow-auto bg-surface-secondary rounded-lg" style={{ height }}>
            {code}
          </pre>
        }
      >
        <MonacoEditor
          height={height}
          language={monacoLang}
          value={code}
          theme={isDark ? "vs-dark" : "vs-light"}
          onChange={(val: string | undefined) => onChange?.(val || "")}
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            automaticLayout: true,
            padding: { top: 12 },
          }}
        />
      </Suspense>
    </div>
  );
}
