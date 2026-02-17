import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language: string;
}

export function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group rounded-lg overflow-hidden bg-surface-tertiary my-2">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-border/30 text-text-secondary text-xs">
        <span className="font-mono">{language || "text"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-text transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check size={14} />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      {/* Code content */}
      <pre className="p-4 overflow-x-auto">
        <code className={`language-${language} text-sm font-mono leading-relaxed`}>
          {code}
        </code>
      </pre>
    </div>
  );
}
