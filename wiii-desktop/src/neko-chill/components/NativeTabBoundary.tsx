import { useEffect, useRef, type ComponentPropsWithoutRef } from "react";
import { tabbable } from "tabbable";

type Props = ComponentPropsWithoutRef<"div"> & { enabled: boolean };

export function nativeTabBoundaryEnabled(active: boolean): boolean {
  // This is a WebKitGTK workaround, not a cross-platform keyboard policy.
  // macOS's implicit button stops depend on the user's keyboard settings.
  return active && typeof window !== "undefined" && "__TAURI_INTERNALS__" in window
    && /^Linux(?:\s|$)/.test(window.navigator.platform);
}

function isPlainTab(event: KeyboardEvent): boolean {
  return !event.defaultPrevented && event.key === "Tab"
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
  useEffect(() => {
    if (!enabled || !rootRef.current) return;
    const doc = rootRef.current.ownerDocument;
    let restoreTimer: ReturnType<typeof setTimeout> | undefined;
    const prepareRelay = (event: KeyboardEvent) => {
      const relay = relayRef.current;
      if (!relay || !isPlainTab(event)) return;
      clearTimeout(restoreTimer);
      // The relay is a forward stop only. Reverse entry can start on BODY,
      // outside React's event path; keep the browser's own navigation anchor.
      relay.tabIndex = event.shiftKey ? -1 : 0;
      if (event.shiftKey) restoreTimer = setTimeout(() => {
        relay.tabIndex = 0;
        restoreTimer = undefined;
      }, 0); // A task (not a microtask) restores it after native default traversal.
    };
    doc.addEventListener("keydown", prepareRelay, true);
    return () => {
      clearTimeout(restoreTimer);
      doc.removeEventListener("keydown", prepareRelay, true);
    };
  }, [enabled]);

  return <div {...props} ref={rootRef} onKeyDown={(event) => {
    onKeyDown?.(event);
    if (!enabled || !event.shiftKey || !isPlainTab(event.nativeEvent)
      || event.currentTarget.ownerDocument.activeElement !== firstControl()) return;
    // Let this same trusted Shift+Tab continue backward from the relay. The
    // browser, not a DOM selector, chooses the last control (including frames).
    goingBackward.current = true;
    try { relayRef.current?.focus({ preventScroll: true }); }
    finally { goingBackward.current = false; }
  }}>
    {children}
    {enabled && <span ref={relayRef} tabIndex={0} aria-hidden="true" data-neko-native-tab-relay=""
      className="pointer-events-none fixed left-0 top-0 h-px w-px opacity-0"
      onFocus={() => {
        if (!goingBackward.current) firstControl()?.focus({ preventScroll: true });
      }} />}
  </div>;
}
