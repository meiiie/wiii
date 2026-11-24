import { useCallback, useEffect, useRef, type ComponentPropsWithoutRef } from "react";
import { tabbable } from "tabbable";

type Props = ComponentPropsWithoutRef<"div"> & { enabled: boolean };

export function nativeTabBoundaryEnabled(active: boolean): boolean {
  // This is a WebKitGTK workaround, not a cross-platform keyboard policy.
  // macOS's implicit button stops depend on the user's keyboard settings.
  return active && typeof window !== "undefined" && "__TAURI_INTERNALS__" in window
    && /^Linux(?:\s|$)/.test(window.navigator.platform);
}

function isBackwardTab(event: KeyboardEvent): boolean {
  return !event.defaultPrevented && event.key === "Tab" && event.shiftKey
    && !event.ctrlKey && !event.altKey && !event.metaKey
    && !event.isComposing && event.keyCode !== 229;
}

/** Keep the native shell's Tab cycle out of GTK's empty webview boundary. */
export function NativeTabBoundary({ enabled, children, onKeyDown, ...props }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const relayRef = useRef<HTMLSpanElement>(null);
  const goingBackward = useRef(false);
  const firstControl = () => rootRef.current
    ? tabbable(rootRef.current).find((node) => node !== relayRef.current)
    : undefined;
  const relayBackward = useCallback(() => {
    goingBackward.current = true;
    try { relayRef.current?.focus({ preventScroll: true }); }
    finally { goingBackward.current = false; }
  }, []);

  useEffect(() => {
    if (!enabled || !rootRef.current) return;
    const doc = rootRef.current.ownerDocument;
    const enterBackward = (event: KeyboardEvent) => {
      if (!isBackwardTab(event)) return;
      // An initial/body keydown never bubbles through the React shell. Put
      // reverse entry before the relay *before* the browser runs its default.
      if (doc.activeElement === doc.body || doc.activeElement === doc.documentElement) relayBackward();
    };
    doc.addEventListener("keydown", enterBackward, true);
    return () => doc.removeEventListener("keydown", enterBackward, true);
  }, [enabled, relayBackward]);

  return <div {...props} ref={rootRef} onKeyDown={(event) => {
    onKeyDown?.(event);
    if (!enabled || !isBackwardTab(event.nativeEvent)
      || event.currentTarget.ownerDocument.activeElement !== firstControl()) return;
    // Let this same trusted Shift+Tab continue backward from the relay. The
    // browser, not a DOM selector, chooses the last control (including frames).
    relayBackward();
  }}>
    {children}
    {enabled && <span ref={relayRef} tabIndex={0} aria-hidden="true" data-neko-native-tab-relay=""
      className="pointer-events-none fixed left-0 top-0 h-px w-px opacity-0"
      onFocus={() => {
        if (!goingBackward.current) firstControl()?.focus({ preventScroll: true });
      }} />}
  </div>;
}
