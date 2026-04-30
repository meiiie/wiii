/**
 * Spotlight tests — overlay creation, tooltip position math, lifecycle.
 */
import { afterEach, describe, expect, it } from "vitest";
import {
  _testing,
  computeTooltipPosition,
  destroySpotlight,
  hideSpotlight,
  showSpotlight,
} from "../spotlight";

afterEach(() => {
  destroySpotlight();
  document.body.innerHTML = "";
});

describe("computeTooltipPosition", () => {
  const viewport = { width: 1024, height: 768 };

  it("places the tooltip below when there is room", () => {
    const target = { left: 100, top: 100, right: 200, bottom: 140, width: 100, height: 40 } as DOMRect;
    const t = { width: 200, height: 60 };
    const pos = computeTooltipPosition(target, t, viewport);
    expect(pos.top).toBe(target.bottom + 12);
  });

  it("flips above when below would overflow", () => {
    const target = { left: 100, top: 700, right: 200, bottom: 740, width: 100, height: 40 } as DOMRect;
    const t = { width: 200, height: 60 };
    const pos = computeTooltipPosition(target, t, viewport);
    expect(pos.top).toBeLessThan(target.top);
  });

  it("clamps left to viewport edges", () => {
    const target = { left: -50, top: 100, right: 50, bottom: 140, width: 100, height: 40 } as DOMRect;
    const t = { width: 200, height: 60 };
    const pos = computeTooltipPosition(target, t, viewport);
    expect(pos.left).toBeGreaterThanOrEqual(8);
  });
});

describe("showSpotlight", () => {
  it("creates overlay + tooltip and writes the message text", () => {
    document.body.innerHTML = `<button data-wiii-id="cta" style="width:100px;height:30px">Bắt đầu</button>`;
    const target = document.querySelector('[data-wiii-id="cta"]')!;
    showSpotlight(target, { message: "Nhấn vào đây để bắt đầu", duration_ms: 1000 });
    const overlay = document.querySelector(`#${_testing.OVERLAY_ID}`) as HTMLDivElement;
    const ring = document.querySelector(`#${_testing.TARGET_RING_ID}`) as HTMLDivElement;
    const tooltip = document.querySelector(`#${_testing.TOOLTIP_ID}`) as HTMLDivElement;
    expect(overlay).not.toBeNull();
    expect(ring).not.toBeNull();
    expect(ring.style.opacity).toBe("1");
    expect(tooltip).not.toBeNull();
    expect(tooltip.textContent).toBe("Nhấn vào đây để bắt đầu");
    expect(overlay.style.background).toContain("radial-gradient");
  });

  it("hideSpotlight clears overlay background", () => {
    document.body.innerHTML = `<button data-wiii-id="x" style="width:50px;height:20px"></button>`;
    showSpotlight(document.querySelector('[data-wiii-id="x"]')!, {
      message: "x",
      duration_ms: 999,
    });
    hideSpotlight();
    const overlay = document.querySelector(`#${_testing.OVERLAY_ID}`) as HTMLDivElement;
    expect(overlay.style.background).toBe("transparent");
  });

  it("does not show tooltip when message is omitted", () => {
    document.body.innerHTML = `<button data-wiii-id="silent"></button>`;
    showSpotlight(document.querySelector('[data-wiii-id="silent"]')!, { duration_ms: 999 });
    const tooltip = document.querySelector(`#${_testing.TOOLTIP_ID}`) as HTMLDivElement;
    expect(tooltip.style.opacity).toBe("0");
  });

  it("destroySpotlight after hideSpotlight is idempotent", () => {
    document.body.innerHTML = `<button data-wiii-id="z"></button>`;
    showSpotlight(document.querySelector('[data-wiii-id="z"]')!, { duration_ms: 999 });
    hideSpotlight();
    expect(() => destroySpotlight()).not.toThrow();
    expect(document.querySelector(`#${_testing.OVERLAY_ID}`)).toBeNull();
  });

  it("rapidly calling show twice keeps only the latest tooltip text", () => {
    document.body.innerHTML = `
      <button id="a">A</button>
      <button id="b">B</button>
    `;
    showSpotlight(document.getElementById("a")!, { message: "first", duration_ms: 1000 });
    showSpotlight(document.getElementById("b")!, { message: "second", duration_ms: 1000 });
    const tooltip = document.querySelector(`#${_testing.TOOLTIP_ID}`) as HTMLDivElement;
    expect(tooltip.textContent).toBe("second");
  });
});

describe("computeTooltipPosition — additional clamps", () => {
  it("clamps to right viewport edge when target is far right", () => {
    const target = { left: 1000, top: 100, right: 1080, bottom: 140, width: 80, height: 40 } as DOMRect;
    const t = { width: 200, height: 60 };
    const viewport = { width: 1024, height: 768 };
    const pos = computeTooltipPosition(target, t, viewport);
    expect(pos.left).toBe(viewport.width - t.width - 8);
  });
  it("places tooltip at viewport top boundary when target near top edge", () => {
    const target = { left: 100, top: 5, right: 200, bottom: 45, width: 100, height: 40 } as DOMRect;
    const t = { width: 200, height: 60 };
    const viewport = { width: 1024, height: 100 };
    const pos = computeTooltipPosition(target, t, viewport);
    // Below would overflow vertical viewport (40+60+12 > 100), so flip above —
    // but above also overflows. Expect clamped to >= 8.
    expect(pos.top).toBeGreaterThanOrEqual(8);
  });
});
