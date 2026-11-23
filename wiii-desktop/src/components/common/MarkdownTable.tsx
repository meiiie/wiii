import { createContext, useContext, useLayoutEffect, useRef, type ComponentProps, type ReactNode } from "react";
import type { ExtraProps } from "react-markdown";

/** Caller-owned, transient reading offsets. Never retain DOM nodes or write chat data. */
export const MarkdownTableScrollPositions = createContext<Map<string, number> | null>(null);
const TableScope = createContext("");

export function MarkdownTableScrollScope({ scope, children }: { scope: string; children: ReactNode }) {
  const parent = useContext(TableScope);
  return <TableScope.Provider value={`${parent}/${encodeURIComponent(scope)}`}>{children}</TableScope.Provider>;
}

export function MarkdownTable({ node, children, ...props }: ComponentProps<"table"> & ExtraProps) {
  const viewport = useRef<HTMLDivElement>(null);
  const positions = useContext(MarkdownTableScrollPositions);
  const scope = useContext(TableScope);
  const key = `${scope}/${node?.position?.start.offset ?? 0}`;

  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element || !positions) return;
    let width = element.clientWidth;
    let extent = element.scrollWidth;
    let applied: number | null = null;
    const restore = () => {
      element.scrollLeft = positions.get(key) ?? 0;
      applied = element.scrollLeft;
    };
    const remember = () => {
      // Resizing may clamp scrollLeft before ResizeObserver runs. Keep the
      // reader's preferred column until the narrower viewport can restore it.
      if (element.clientWidth !== width || element.scrollWidth !== extent
        || (applied !== null && Math.abs(element.scrollLeft - applied) < 1)) return;
      applied = null;
      positions.set(key, element.scrollLeft);
    };
    restore();
    element.addEventListener("scroll", remember);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      width = element.clientWidth;
      extent = element.scrollWidth;
      restore();
    });
    observer?.observe(element);
    if (element.firstElementChild) observer?.observe(element.firstElementChild);
    return () => {
      element.removeEventListener("scroll", remember);
      observer?.disconnect();
    };
  }, [positions, key]);

  return (
    <div ref={viewport} className="wiii-table-viewport" role="region" aria-label="Bảng" tabIndex={0}>
      <table {...props}>{children}</table>
    </div>
  );
}
