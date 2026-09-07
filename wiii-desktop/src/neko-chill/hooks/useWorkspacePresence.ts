import { useLayoutEffect, useRef, useState } from "react";

export function useWorkspacePresence(open: boolean, identity: string) {
  const [retained, setRetained] = useState<string | null>(open ? identity : null);
  const ref = useRef<HTMLDivElement>(null);
  const interrupted = useRef<{ element: HTMLDivElement; identity: string; opacity: string; transform: string } | null>(null);

  useLayoutEffect(() => {
    if (open) setRetained(identity);
    const element = ref.current;
    const motionPreference = typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;
    if (element) element.inert = !open;
    if (!element || !element.animate || !motionPreference || motionPreference.matches) {
      interrupted.current = null;
      if (!open) setRetained(null);
      return;
    }

    const previous = interrupted.current;
    interrupted.current = null;
    const from = previous?.element === element && previous.identity === identity
      ? { opacity: previous.opacity, transform: previous.transform }
      : { opacity: open ? 0 : 1, transform: `translateX(${open ? 6 : 0}px)` };
    const animation = element.animate([
      from,
      { opacity: open ? 1 : 0, transform: `translateX(${open ? 0 : 6}px)` },
    ], { duration: 140, easing: "cubic-bezier(0.2, 0, 0, 1)", fill: "both" });
    let completed = false;
    let cancelled = false;
    const finish = () => {
      if (cancelled || completed) return;
      completed = true;
      motionPreference.removeEventListener("change", onMotionChange);
      animation.cancel();
      if (!open) setRetained((current) => current === identity ? null : current);
    };
    const onMotionChange = () => {
      if (motionPreference.matches) finish();
    };
    animation.onfinish = finish;
    motionPreference.addEventListener("change", onMotionChange);
    return () => {
      cancelled = true;
      motionPreference.removeEventListener("change", onMotionChange);
      if (!completed && element.isConnected) {
        const style = getComputedStyle(element);
        interrupted.current = { element, identity, opacity: style.opacity, transform: style.transform };
      }
      animation.onfinish = null;
      animation.cancel();
    };
  }, [identity, open]);

  return { present: open || retained === identity, ref };
}
