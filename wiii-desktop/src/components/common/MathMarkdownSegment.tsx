import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import "katex/dist/katex.min.css";
import { markdownRenderComponents } from "./markdown-render-components";
import { mathSanitizeSchema } from "./markdown-sanitize-schema";

interface MathMarkdownSegmentProps {
  content: string;
}

export function MathMarkdownSegment({ content }: MathMarkdownSegmentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[
        rehypeRaw,
        [rehypeKatex, { strict: false, throwOnError: false }],
        [rehypeSanitize, mathSanitizeSchema],
      ]}
      components={markdownRenderComponents}
    >
      {content}
    </ReactMarkdown>
  );
}
