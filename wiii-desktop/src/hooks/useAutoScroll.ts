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
  const followFrameRef = useRef(0);
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

  const scheduleFollow = useCallback(() => {
    if (!containerRef.current || isUserScrolledUp.current || followFrameRef.current) return;
    followFrameRef.current = requestAnimationFrame(() => {
      followFrameRef.current = 0;
      const container = containerRef.current;
      if (!container || isUserScrolledUp.current) return;
      container.scrollTo({ top: container.scrollHeight, behavior: "auto" });
    });
  }, []);

  useEffect(scheduleFollow, [dependency, scheduleFollow]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const resize = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(scheduleFollow);
    const observeContent = () => {
      resize?.disconnect();
      resize?.observe(container);
      for (const child of container.children) resize?.observe(child);
      scheduleFollow();
    };
    observeContent();
    const children = new MutationObserver(observeContent);
    children.observe(container, { childList: true });
    return () => {
      children.disconnect();
      resize?.disconnect();
      if (followFrameRef.current) cancelAnimationFrame(followFrameRef.current);
      followFrameRef.current = 0;
    };
  }, [scheduleFollow]);

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
