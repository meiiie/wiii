interface ReadingAnchor {
  node: Node;
  offset: number;
  edge?: "top" | "bottom";
  measure: () => DOMRect | null;
}

/** Keep a text position, not a scroll percentage: wrapping changes earlier rows. */
export function captureTranscriptReadingAnchor(viewport: HTMLElement): ReadingAnchor | null {
  const bounds = viewport.getBoundingClientRect();
  if (bounds.width <= 0 || bounds.height <= 0) return null;
  const readingLine = bounds.top + Math.min(12, bounds.height / 2);
  const range = viewport.ownerDocument.caretRangeFromPoint?.(
    bounds.left + Math.min(160, bounds.width / 3), readingLine,
  );
  if (range && viewport.contains(range.startContainer) && typeof range.getBoundingClientRect === "function") {
    // Some WebKit builds give collapsed carets an empty rect. Measure one
    // adjacent character without changing DOM, focus or the user's selection.
    const node = range.startContainer;
    if (range.collapsed && node.nodeType === Node.TEXT_NODE) {
      if (range.startOffset < (node.textContent?.length ?? 0)) range.setEnd(node, range.startOffset + 1);
      else if (range.startOffset > 0) range.setStart(node, range.startOffset - 1);
    }
    const rect = range.getBoundingClientRect();
    if (rect.height > 0 && rect.bottom > bounds.top && rect.top < bounds.bottom) {
      // Text.data replacement (including streaming appends) resets a live
      // Range's offsets to zero. Keep immutable boundaries, not its live caret.
      const startNode = range.startContainer;
      const endNode = range.endContainer;
      const startOffset = range.startOffset;
      const endOffset = range.endOffset;
      const length = (node: Node) => node.nodeType === Node.TEXT_NODE ? node.textContent?.length ?? 0 : node.childNodes.length;
      return {
        node: startNode, offset: rect.top - bounds.top,
        measure: () => {
          if (!endNode.isConnected || !viewport.contains(endNode)
            || startOffset > length(startNode) || endOffset > length(endNode)) return null;
          range.setStart(startNode, startOffset);
          range.setEnd(endNode, endOffset);
          return range.getBoundingClientRect();
        },
      };
    }
  }

  // Fallback for engines without point-to-text ranges. Remove visible enclosing
  // containers first: their large boxes also cover the gaps between paragraphs.
  const visible = new Map<HTMLElement, DOMRect>();
  for (const element of viewport.querySelectorAll<HTMLElement>(
    "p,li,pre,blockquote,h1,h2,h3,h4,h5,h6,td,th,[data-neko-message-index]",
  )) {
    const rect = element.getBoundingClientRect();
    if (rect.height > 0 && rect.bottom > bounds.top && rect.top < bounds.bottom) visible.set(element, rect);
  }
  const containers = new Set<HTMLElement>();
  for (const element of visible.keys()) {
    for (let parent = element.parentElement; parent && parent !== viewport; parent = parent.parentElement) {
      if (visible.has(parent)) containers.add(parent);
    }
  }
  const best: { element: HTMLElement | null; distance: number } = { element: null, distance: Infinity };
  for (const [element, rect] of visible) {
    if (containers.has(element)) continue;
    const nextDistance = Math.max(rect.top - readingLine, readingLine - rect.bottom, 0);
    if (nextDistance < best.distance) {
      best.element = element;
      best.distance = nextDistance;
    }
  }
  const element = best.element;
  if (!element) return null;
  const rect = visible.get(element)!;
  const edge = rect.bottom < readingLine ? "bottom" : "top";
  return { node: element, edge, offset: rect[edge] - bounds.top, measure: () => element.getBoundingClientRect() };
}

export function restoreTranscriptReadingAnchor(viewport: HTMLElement, anchor: ReadingAnchor | null): boolean {
  // Virtualization/content replacement may have removed the old node. Never
  // scroll to a detached node or reuse an anchor from another conversation.
  if (!anchor?.node.isConnected || !viewport.contains(anchor.node)) return false;
  const bounds = anchor.measure();
  if (!bounds || bounds.height <= 0) return false;
  const delta = bounds[anchor.edge ?? "top"] - viewport.getBoundingClientRect().top - anchor.offset;
  if (!Number.isFinite(delta)) return false;
  if (Math.abs(delta) > 0.5) viewport.scrollTop += delta;
  return true;
}
