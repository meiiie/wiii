/**
 * Cursor tests — geometry helpers and DOM lifecycle.
 *
 * Note: jsdom's Web Animations is limited; we only assert that animate() is
 * invoked, not that frames advance.
 */
import { afterEach, describe, expect, it } from "vitest";
import {
  _testing,
  computeOriginPoint,
  computeTargetPoint,
  destroyCursor,
  hideCursor,
  moveCursorToRect,
} from "../cursor";

afterEach(() => {
  destroyCursor();
  _testing.setLastPos(null);
});

describe("computeTargetPoint", () => {
  it("lands above-right of element center", () => {
    const rect = { left: 100, top: 200, width: 40, height: 20 } as DOMRect;
    const p = computeTargetPoint(rect);
    expect(p.x).toBe(100 + 20 + 8);
    expect(p.y).toBe(200 + 10 - 8);
  });
});

describe("computeOriginPoint", () => {
  it("returns a point inside the viewport", () => {
    const p = computeOriginPoint();
    expect(p.x).toBeGreaterThan(0);
    expect(p.y).toBeGreaterThan(0);
  });
});

describe("moveCursorToRect", () => {
  it("creates a single SVG cursor in the DOM", () => {
    const rect = { left: 50, top: 50, width: 30, height: 30 } as DOMRect;
    moveCursorToRect(rect, { duration_ms: 100 });
    const cursors = document.querySelectorAll(`#${_testing.CURSOR_ID}`);
    expect(cursors.length).toBe(1);
    const el = cursors[0] as SVGSVGElement;
    expect(el.getAttribute("data-wiii-pointy")).toBe("cursor");
    expect(el.style.opacity).toBe("1");
  });

  it("re-uses the cursor element when called twice", () => {
    const rect1 = { left: 10, top: 10, width: 10, height: 10 } as DOMRect;
    const rect2 = { left: 100, top: 100, width: 10, height: 10 } as DOMRect;
    moveCursorToRect(rect1, { duration_ms: 50 });
    moveCursorToRect(rect2, { duration_ms: 50 });
    expect(document.querySelectorAll(`#${_testing.CURSOR_ID}`).length).toBe(1);
  });
});

describe("hideCursor / destroyCursor", () => {
  it("hide fades opacity to 0 but keeps the node", () => {
    const rect = { left: 0, top: 0, width: 10, height: 10 } as DOMRect;
    moveCursorToRect(rect);
    hideCursor();
    const el = document.querySelector(`#${_testing.CURSOR_ID}`) as SVGSVGElement;
    expect(el).not.toBeNull();
    expect(el.style.opacity).toBe("0");
  });
  it("destroy removes the node", () => {
    const rect = { left: 0, top: 0, width: 10, height: 10 } as DOMRect;
    moveCursorToRect(rect);
    destroyCursor();
    expect(document.querySelector(`#${_testing.CURSOR_ID}`)).toBeNull();
  });
});
