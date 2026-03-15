import { type ReactNode, lazy, Suspense } from "react";

const MermaidDiagram = lazy(() => import("./MermaidDiagram"));
const InlineHtmlWidget = lazy(() => import("./InlineHtmlWidget"));
const LazyCodeBlock = lazy(async () => {
  const mod = await import("./CodeBlock");
  return { default: mod.CodeBlock };
});

function extractText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string") return node;
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (typeof node === "object" && "props" in node) {
    return extractText((node as { props: { children?: ReactNode } }).props.children);
  }
  return "";
}

export const markdownRenderComponents = {
  code({ className: codeClassName, children, ...props }: {
    className?: string;
    children?: ReactNode;
  }) {
    const match = /language-(\w+)/.exec(codeClassName || "");
    const isInline = !match;

    if (isInline) {
      return (
        <code className={codeClassName} {...props}>
          {children}
        </code>
      );
    }

    const rawCode = extractText(children).replace(/\n$/, "");

    if (match[1] === "mermaid") {
      return (
        <Suspense fallback={<pre className="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm"><code>{rawCode}</code></pre>}>
          <MermaidDiagram code={rawCode} />
        </Suspense>
      );
    }

    if (match[1] === "widget") {
      return (
        <Suspense fallback={<div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm animate-pulse">Dang tai widget...</div>}>
          <InlineHtmlWidget code={rawCode} />
        </Suspense>
      );
    }

    return (
      <Suspense
        fallback={(
          <pre className="my-2 overflow-x-auto rounded-lg border border-[var(--border)] bg-white/50 p-4">
            <code className="text-sm font-mono leading-relaxed">{rawCode}</code>
          </pre>
        )}
      >
        <LazyCodeBlock language={match[1] || ""} code={rawCode} />
      </Suspense>
    );
  },
};
