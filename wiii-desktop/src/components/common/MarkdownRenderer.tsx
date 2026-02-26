import { type ReactNode, lazy, Suspense } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import "katex/dist/katex.min.css";
import { CodeBlock } from "./CodeBlock";

const MermaidDiagram = lazy(() => import("./MermaidDiagram"));

/**
 * Extended sanitize schema — allows KaTeX-generated HTML elements.
 * KaTeX produces complex HTML with MathML elements, styled spans, and aria attrs.
 * Without this, rehype-sanitize strips the rendered math output.
 */
const mathSanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    // KaTeX MathML elements
    "math", "semantics", "mrow", "mi", "mn", "mo", "mover", "munder", "munderover",
    "msup", "msub", "msubsup", "mfrac", "msqrt", "mroot", "mtable",
    "mtr", "mtd", "mtext", "mspace", "annotation", "mpadded", "menclose",
    // Extra markdown
    "mark", "del", "ins",
  ],
  attributes: {
    ...defaultSchema.attributes,
    div: [...(defaultSchema.attributes?.div || []), "className", "style"],
    span: [...(defaultSchema.attributes?.span || []), "className", "style", "aria-hidden"],
    math: ["xmlns", "display"],
    annotation: ["encoding"],
  },
};

/**
 * Extract raw text from React children tree.
 * Rehype plugins (katex, sanitize) may wrap code in React elements,
 * so `String(children)` returns "[object Object]". This recursively
 * extracts the actual text content for CodeBlock.
 */
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

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content selectable ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[
          rehypeRaw,
          [rehypeKatex, { strict: false, throwOnError: false }],
          [rehypeSanitize, mathSanitizeSchema],
        ]}
        components={{
          code({ className: codeClassName, children, ...props }) {
            const match = /language-(\w+)/.exec(codeClassName || "");
            const isInline = !match;

            if (isInline) {
              return (
                <code className={codeClassName} {...props}>
                  {children}
                </code>
              );
            }

            // Extract raw text — rehype plugins may wrap children in React elements
            const rawCode = extractText(children).replace(/\n$/, "");

            // Sprint 179: Route mermaid code blocks to MermaidDiagram
            if (match && match[1] === "mermaid") {
              return (
                <Suspense fallback={<pre className="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm"><code>{rawCode}</code></pre>}>
                  <MermaidDiagram code={rawCode} />
                </Suspense>
              );
            }

            return (
              <CodeBlock
                language={match?.[1] || ""}
                code={rawCode}
              />
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
