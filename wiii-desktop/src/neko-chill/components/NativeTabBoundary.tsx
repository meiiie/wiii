import { useCallback, useEffect, useRef, type ComponentPropsWithoutRef } from "react";
import { tabbable } from "tabbable";

type Props = ComponentPropsWithoutRef<"div"> & { enabled: boolean };

export function nativeTabBoundaryEnabled(active: boolean): boolean {
  // This is a WebKitGTK workaround, not a cross-platform keyboard policy.
  // macOS's implicit button stops depend on the user's keyboard settings.
  return active && typeof window !== "undefined" && "__TAURI_INTERNALS__" in window
    && /^Linux(?:\s|$)/.test(window.navigator.platform);
}

export function isPlainTab(event: KeyboardEvent): boolean {
  // WebKitGTK can label trusted Shift+Tab "Unidentified" while preserving its
  // physical Tab code. Do not override a different identified/remapped key.
  const tab = event.key === "Tab" || (event.key === "Unidentified" && event.code === "Tab");
  return !event.defaultPrevented && tab
    && !event.ctrlKey && !event.altKey && !event.metaKey
    && !event.isComposing && event.keyCode !== 229;
}

/** Keep the native shell's Tab cycle out of GTK's empty webview boundary. */
export function NativeTabBoundary({ enabled, children, onKeyDown, onPointerDownCapture, onFocusCapture, ...props }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const relayRef = useRef<HTMLSpanElement>(null);
  const goingBackward = useRef(false);
  const pointerAnchor = useRef<Node | null>(null);
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
    let restoreTimer: ReturnType<typeof setTimeout> | undefined;
    const prepareRelay = (event: KeyboardEvent) => {
      const relay = relayRef.current;
      if (!relay || !isPlainTab(event)) return;
      clearTimeout(restoreTimer);
      // The relay is a forward stop only. Reverse entry can start on BODY,
      // outside React's event path; keep the browser's own navigation anchor.
      relay.tabIndex = event.shiftKey ? -1 : 0;
      const anchor = pointerAnchor.current;
      const first = event.shiftKey ? firstControl() : undefined;
      // A passive click before the first control (e.g. a notice title) is
      // another reverse edge, not a reason to hand focus to GTK. Mid-page
      // text anchors remain browser-owned; a real control focus clears this.
      if (event.shiftKey && doc.activeElement === doc.body && anchor && first
        && rootRef.current?.contains(anchor)
        && (anchor.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING)) relayBackward();
      if (event.shiftKey) restoreTimer = setTimeout(() => {
        relay.tabIndex = 0;
        restoreTimer = undefined;
      }, 0); // A task (not a microtask) restores it after native default traversal.
    };
    doc.addEventListener("keydown", prepareRelay, true);
    return () => {
      clearTimeout(restoreTimer);
      pointerAnchor.current = null;
      doc.removeEventListener("keydown", prepareRelay, true);
    };
  }, [enabled, relayBackward]);

  return <div {...props} ref={rootRef} onPointerDownCapture={(event) => {
    onPointerDownCapture?.(event);
    if (enabled && !event.defaultPrevented && event.target instanceof Node) pointerAnchor.current = event.target;
  }} onFocusCapture={(event) => {
    onFocusCapture?.(event);
    if (enabled) pointerAnchor.current = null;
  }} onKeyDown={(event) => {
    onKeyDown?.(event);
    if (!enabled || !event.shiftKey || !isPlainTab(event.nativeEvent)
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
