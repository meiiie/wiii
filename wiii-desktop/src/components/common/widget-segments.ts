export interface ContentSegment {
  type: "markdown" | "widget";
  content: string;
  pending?: boolean;
}

export function splitWidgetBlocks(raw: string): ContentSegment[] {
  const segments: ContentSegment[] = [];
  const widgetStartRe = /```widget[ \t]*\r?\n/g;
  const widgetEndRe = /\r?\n```(?:\s|$)/;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  const pushMarkdown = (value: string) => {
    const trimmed = value.trim();
    if (trimmed) segments.push({ type: "markdown", content: trimmed });
  };

  while ((match = widgetStartRe.exec(raw)) !== null) {
    const widgetStart = match.index;
    const widgetBodyStart = match.index + match[0].length;
    const widgetTail = raw.slice(widgetBodyStart);
    const closeMatch = widgetTail.match(widgetEndRe);

    if (widgetStart > lastIndex) {
      pushMarkdown(raw.slice(lastIndex, widgetStart));
    }

    if (!closeMatch || typeof closeMatch.index !== "number") {
      segments.push({
        type: "widget",
        content: widgetTail.trim(),
        pending: true,
      });
      lastIndex = raw.length;
      break;
    }

    const widgetEnd = widgetBodyStart + closeMatch.index;
    const widgetHtml = raw.slice(widgetBodyStart, widgetEnd).trim();

    if (widgetHtml.includes("<")) {
      segments.push({ type: "widget", content: widgetHtml });
    } else {
      const rawBlock = raw.slice(widgetStart, widgetEnd + closeMatch[0].length);
      pushMarkdown(rawBlock);
    }

    lastIndex = widgetEnd + closeMatch[0].length;
    widgetStartRe.lastIndex = lastIndex;
  }

  if (lastIndex < raw.length) {
    pushMarkdown(raw.slice(lastIndex));
  }

  if (segments.length === 0) {
    segments.push({ type: "markdown", content: raw });
  }

  return segments;
}
