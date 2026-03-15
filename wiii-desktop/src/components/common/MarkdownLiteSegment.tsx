import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { markdownRenderComponents } from "./markdown-render-components";

interface MarkdownLiteSegmentProps {
  content: string;
}

export function MarkdownLiteSegment({ content }: MarkdownLiteSegmentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={markdownRenderComponents}
    >
      {content}
    </ReactMarkdown>
  );
}
