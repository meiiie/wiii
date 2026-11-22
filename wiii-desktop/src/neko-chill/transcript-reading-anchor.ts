interface ReadingAnchor {
  node: Node;
  offset: number;
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
  if (range && range.startContainer.nodeType === Node.TEXT_NODE
    && viewport.contains(range.startContainer) && typeof range.getBoundingClientRect === "function") {
    // Some WebKit builds give collapsed carets an empty rect. Measure one
    // adjacent character without changing DOM, focus or the user's selection.
    const node = range.startContainer;
    if (range.collapsed && node.nodeType === Node.TEXT_NODE) {
      if (range.startOffset < (node.textContent?.length ?? 0)) range.setEnd(node, range.startOffset + 1);
      else if (range.startOffset > 0) range.setStart(node, range.startOffset - 1);
    }
    const anchor = anchorFromRange(viewport, range, bounds);
    if (anchor) return anchor;
  }

  // A parent list item can own text as well as nested blocks. Element boxes
  // cannot distinguish that text from gaps or children; measure text directly.
  const probe = viewport.ownerDocument.createRange();
  if (typeof probe.getBoundingClientRect !== "function") return null;
  const walker = viewport.ownerDocument.createTreeWalker(viewport, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      if (node.nodeType === Node.TEXT_NODE) return node.textContent?.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      const element = node as HTMLElement;
      if (element.matches("[hidden],[aria-hidden='true'],.sr-only,script,style")) return NodeFilter.FILTER_REJECT;
      const rect = element.getBoundingClientRect();
      // Prune off-screen branches, not zero-box wrappers (display: contents).
      if (rect.height > 0 && (rect.bottom <= bounds.top || rect.top >= bounds.bottom)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_SKIP;
    },
  });
  const best: { node: Node | null; distance: number; rect: DOMRect | null } = { node: null, distance: Infinity, rect: null };
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    probe.selectNodeContents(node);
    const rect = probe.getBoundingClientRect();
    if (rect.height <= 0 || rect.bottom <= bounds.top || rect.top >= bounds.bottom) continue;
    const nextDistance = Math.max(rect.top - readingLine, readingLine - rect.bottom, 0);
    if (nextDistance < best.distance) {
      best.node = node;
      best.distance = nextDistance;
      best.rect = rect;
      if (nextDistance === 0) break;
    }
  }
  if (!best.node || !best.rect) return null;
  const node = best.node;
  let low = 0;
  let high = (node.textContent?.length ?? 1) - 1;
  if (best.rect.bottom <= readingLine) low = high;
  else if (best.rect.top >= readingLine) high = 0;
  // Find the first character on the reading line without scanning every glyph.
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    probe.setStart(node, middle); probe.setEnd(node, middle + 1);
    if (probe.getBoundingClientRect().bottom <= readingLine) low = middle + 1;
    else high = middle;
  }
  probe.setStart(node, low); probe.setEnd(node, low + 1);
  return anchorFromRange(viewport, probe, bounds);
}

function anchorFromRange(viewport: HTMLElement, range: Range, bounds: DOMRect): ReadingAnchor | null {
  const rect = range.getBoundingClientRect();
  if (rect.height <= 0 || rect.bottom <= bounds.top || rect.top >= bounds.bottom) return null;
  // Text.data replacement (including streaming appends) resets live offsets.
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

export function restoreTranscriptReadingAnchor(viewport: HTMLElement, anchor: ReadingAnchor | null): boolean {
  // Virtualization/content replacement may have removed the old node. Never
  // scroll to a detached node or reuse an anchor from another conversation.
  if (!anchor?.node.isConnected || !viewport.contains(anchor.node)) return false;
  const bounds = anchor.measure();
  if (!bounds || bounds.height <= 0) return false;
  const delta = bounds.top - viewport.getBoundingClientRect().top - anchor.offset;
  if (!Number.isFinite(delta)) return false;
  if (Math.abs(delta) > 0.5) viewport.scrollTop += delta;
  return true;
}
