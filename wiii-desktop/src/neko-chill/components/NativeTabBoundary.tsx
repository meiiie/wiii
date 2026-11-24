import { useRef, type ComponentPropsWithoutRef } from "react";
import { tabbable } from "tabbable";

type Props = ComponentPropsWithoutRef<"div"> & { enabled: boolean };

/** Keep the native shell's Tab cycle out of GTK's empty webview boundary. */
export function NativeTabBoundary({ enabled, children, onKeyDown, ...props }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const relayRef = useRef<HTMLSpanElement>(null);
  const goingBackward = useRef(false);
  const firstControl = () => rootRef.current
    ? tabbable(rootRef.current).find((node) => node !== relayRef.current)
    : undefined;

  return <div {...props} ref={rootRef} onKeyDown={(event) => {
    onKeyDown?.(event);
    if (!enabled || event.defaultPrevented || event.key !== "Tab" || !event.shiftKey
      || event.ctrlKey || event.altKey || event.metaKey
      || event.nativeEvent.isComposing || event.keyCode === 229) return;
    const relay = relayRef.current;
    if (!relay || event.currentTarget.ownerDocument.activeElement !== firstControl()) return;
    // Let this same trusted Shift+Tab continue backward from the relay. The
    // browser, not a DOM selector, chooses the last control (including frames).
    goingBackward.current = true;
    try { relay.focus({ preventScroll: true }); }
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
