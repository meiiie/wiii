import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import { markdownRenderComponents } from "./markdown-render-components";
import { baseSanitizeSchema } from "./markdown-sanitize-schema";

interface RichMarkdownSegmentProps {
  content: string;
}

export function RichMarkdownSegment({ content }: RichMarkdownSegmentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[
        rehypeRaw,
        [rehypeSanitize, baseSanitizeSchema],
      ]}
      components={markdownRenderComponents}
    >
      {content}
    </ReactMarkdown>
  );
}
