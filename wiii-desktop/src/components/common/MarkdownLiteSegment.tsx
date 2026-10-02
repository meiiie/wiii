import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { createMarkdownRenderComponents } from "./markdown-render-components";

interface MarkdownLiteSegmentProps {
  content: string;
  streaming?: boolean;
}

export function MarkdownLiteSegment({ content, streaming = false }: MarkdownLiteSegmentProps) {
  const components = useMemo(() => createMarkdownRenderComponents(streaming), [streaming]);
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={components}
    >
      {content}
    </ReactMarkdown>
  );
}
