/**
 * Auto-scroll hook — scrolls to bottom during streaming,
 * pauses when user scrolls up.
 * Sprint 81: Expose isAtBottom for scroll-to-bottom FAB.
 * Sprint 104: Slight delay for animation settle before smooth scroll.
 */
import { useEffect, useRef, useCallback, useState } from "react";

export function useAutoScroll(dependency: unknown) {
  const containerRef = useRef<HTMLDivElement>(null);
  const isUserScrolledUp = useRef(false);
  const scrollFrameRef = useRef(0);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior,
      });
      isUserScrolledUp.current = false;
      setIsAtBottom(true);
    }
  }, []);

  // Follow streamed content once per paint. Smooth scrolling per token creates
  // overlapping animations and makes the transcript feel delayed.
  useEffect(() => {
    if (!containerRef.current || isUserScrolledUp.current) return;
    const frame = requestAnimationFrame(() => {
      const container = containerRef.current;
      if (!container || isUserScrolledUp.current) return;
      container.scrollTo({ top: container.scrollHeight, behavior: "auto" });
    });
    return () => cancelAnimationFrame(frame);
  }, [dependency]);

  // Detect user scroll
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const syncScrollState = () => {
      scrollFrameRef.current = 0;
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      const atBottom = distanceFromBottom <= 200;
      isUserScrolledUp.current = !atBottom;
      setIsAtBottom((current) => current === atBottom ? current : atBottom);
    };
    const handleScroll = () => {
      if (scrollFrameRef.current) return;
      scrollFrameRef.current = requestAnimationFrame(syncScrollState);
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
      if (scrollFrameRef.current) cancelAnimationFrame(scrollFrameRef.current);
      scrollFrameRef.current = 0;
    };
  }, []);

  return { containerRef, scrollToBottom, isAtBottom };
}
