import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import { createMarkdownRenderComponents } from "./markdown-render-components";
import { baseSanitizeSchema } from "./markdown-sanitize-schema";

interface RichMarkdownSegmentProps {
  content: string;
  streaming?: boolean;
}

export function RichMarkdownSegment({ content, streaming = false }: RichMarkdownSegmentProps) {
  const components = useMemo(() => createMarkdownRenderComponents(streaming), [streaming]);
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[
        rehypeRaw,
        [rehypeSanitize, baseSanitizeSchema],
      ]}
      components={components}
    >
      {content}
    </ReactMarkdown>
  );
}
