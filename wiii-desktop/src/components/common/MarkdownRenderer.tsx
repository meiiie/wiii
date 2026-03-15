import { lazy, Suspense } from "react";
import { splitWidgetBlocks } from "./widget-segments";

const InlineHtmlWidget = lazy(() => import("./InlineHtmlWidget"));
const RichMarkdownSegment = lazy(async () => {
  const mod = await import("./RichMarkdownSegment");
  return { default: mod.RichMarkdownSegment };
});
const MarkdownLiteSegment = lazy(async () => {
  const mod = await import("./MarkdownLiteSegment");
  return { default: mod.MarkdownLiteSegment };
});
const MathMarkdownSegment = lazy(async () => {
  const mod = await import("./MathMarkdownSegment");
  return { default: mod.MathMarkdownSegment };
});

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

function PendingWidgetSegment() {
  return (
    <div
      className="rounded-[24px] border border-[color-mix(in_srgb,var(--border)_78%,white)] bg-[linear-gradient(180deg,rgba(255,255,255,0.84),rgba(248,244,236,0.76))] px-5 py-5 text-sm text-text-secondary shadow-[var(--shadow-sm)]"
      data-testid="pending-inline-widget"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-tertiary">
        Dang dung widget
      </p>
      <p className="mt-2 leading-6">
        Wiii dang hoan thien khung tuong tac de chen vao ngay trong cau tra loi.
      </p>
    </div>
  );
}

function shouldUseRichMarkdown(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) return false;

  return (
    /```|~~~/.test(trimmed) ||
    /(^|\n)\s{0,3}(#{1,6}\s|[-*+]\s|>\s|\d+[.)]\s)/m.test(trimmed) ||
    /!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\)/.test(trimmed) ||
    /(^|\n)\|.+\|/m.test(trimmed) ||
    /\bhttps?:\/\/\S+/i.test(trimmed) ||
    /\$\$?/.test(trimmed) ||
    /[*_~`]/.test(trimmed) ||
    /<\/?[A-Za-z][^>]*>/.test(trimmed)
  );
}

function shouldUseMathMarkdown(content: string): boolean {
  return (
    /\$\$[\s\S]+?\$\$/.test(content)
    || /(^|[^\\])\$[^$\n]+\$/.test(content)
    || /\\\(|\\\[/.test(content)
  );
}

function shouldUseHtmlMarkdown(content: string): boolean {
  return /<\/?[A-Za-z][^>]*>/.test(content);
}

function PlainTextSegment({ content }: { content: string }) {
  const paragraphs = content
    .split(/\n\s*\n+/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (paragraphs.length === 0) return null;

  return (
    <div className="markdown-plain space-y-4">
      {paragraphs.map((paragraph, index) => (
        <p key={`${index}-${paragraph.slice(0, 24)}`} className="whitespace-pre-wrap">
          {paragraph}
        </p>
      ))}
    </div>
  );
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  const segments = splitWidgetBlocks(content);

  return (
    <div className={`markdown-content selectable ${className}`}>
      {segments.map((seg, i) => {
        if (seg.type === "widget") {
          if (seg.pending) {
            return <PendingWidgetSegment key={`widget-pending-${i}`} />;
          }
          return (
            <Suspense
              key={`widget-${i}`}
              fallback={<div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm animate-pulse">Dang tai widget...</div>}
            >
              <InlineHtmlWidget code={seg.content} widgetId={`legacy-widget-${i}`} />
            </Suspense>
          );
        }

        if (!shouldUseRichMarkdown(seg.content)) {
          return <PlainTextSegment key={`plain-${i}`} content={seg.content} />;
        }

        const SegmentComponent = shouldUseMathMarkdown(seg.content)
          ? MathMarkdownSegment
          : shouldUseHtmlMarkdown(seg.content)
            ? RichMarkdownSegment
            : MarkdownLiteSegment;

        return (
          <Suspense
            key={`md-${i}`}
            fallback={<PlainTextSegment content={seg.content} />}
          >
            <SegmentComponent content={seg.content} />
          </Suspense>
        );
      })}
    </div>
  );
}
