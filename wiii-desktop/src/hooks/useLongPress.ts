/**
 * useLongPress — detect long-press (touch hold) gesture.
 * Sprint 162b: Touch-friendly conversation actions.
 *
 * Usage:
 *   const handlers = useLongPress(() => setMenuOpen(true), { delay: 500 });
 *   <div {...handlers}>...</div>
 */
import { useRef, useCallback } from "react";

interface LongPressOptions {
  /** Milliseconds before long-press fires (default 500) */
  delay?: number;
  /** Movement threshold in px that cancels the press (default 10) */
  moveThreshold?: number;
}

interface LongPressHandlers {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: () => void;
  onTouchCancel: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

export function useLongPress(
  onLongPress: () => void,
  options: LongPressOptions = {},
): LongPressHandlers {
  const { delay = 500, moveThreshold = 10 } = options;
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const startPos = useRef<{ x: number; y: number } | null>(null);
  const firedRef = useRef(false);

  const clear = useCallback(() => {
    clearTimeout(timerRef.current);
    timerRef.current = undefined;
    startPos.current = null;
    firedRef.current = false;
  }, []);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      firedRef.current = false;
      const touch = e.touches[0];
      startPos.current = { x: touch.clientX, y: touch.clientY };
      timerRef.current = setTimeout(() => {
        firedRef.current = true;
        onLongPress();
      }, delay);
    },
    [onLongPress, delay],
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!startPos.current) return;
      const touch = e.touches[0];
      const dx = touch.clientX - startPos.current.x;
      const dy = touch.clientY - startPos.current.y;
      if (Math.abs(dx) > moveThreshold || Math.abs(dy) > moveThreshold) {
        clear();
      }
    },
    [moveThreshold, clear],
  );

  const onTouchEnd = useCallback(() => {
    clear();
  }, [clear]);

  const onTouchCancel = useCallback(() => {
    clear();
  }, [clear]);

  // Prevent native context menu on long-press (mobile browsers)
  const onContextMenu = useCallback((e: React.MouseEvent) => {
    if (firedRef.current) {
      e.preventDefault();
    }
  }, []);

  return { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel, onContextMenu };
}
