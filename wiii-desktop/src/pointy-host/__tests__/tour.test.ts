/**
 * Tour tests — step progression, missing selectors, cancellation.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _testing, runTour } from "../tour";
import type { TourStep } from "../types";

beforeEach(() => {
  _testing.resetState();
});

afterEach(() => {
  _testing.resetState();
  document.body.innerHTML = "";
  vi.useRealTimers();
});

describe("runTour", () => {
  it("walks through all steps with present selectors", async () => {
    document.body.innerHTML = `
      <div id="a" style="height:10px"></div>
      <div id="b" style="height:10px"></div>
    `;
    const steps: TourStep[] = [
      { selector: "#a", message: "A", duration_ms: 1 },
      { selector: "#b", message: "B", duration_ms: 1 },
    ];
    const result = await runTour(steps);
    expect(result.completed_steps).toBe(2);
    expect(result.total_steps).toBe(2);
    expect(result.cancelled).toBe(false);
    expect(result.missing_selectors).toEqual([]);
  });

  it("collects missing selectors without aborting", async () => {
    document.body.innerHTML = `<div id="present"></div>`;
    const steps: TourStep[] = [
      { selector: "#present", message: "present", duration_ms: 1 },
      { selector: "#missing", message: "missing", duration_ms: 1 },
    ];
    const result = await runTour(steps);
    expect(result.completed_steps).toBe(1);
    expect(result.missing_selectors).toEqual(["#missing"]);
  });

  it("starting a new tour cancels the previous one", async () => {
    document.body.innerHTML = `<div id="a"></div>`;
    const longStep: TourStep[] = [{ selector: "#a", message: "long", duration_ms: 200 }];
    const firstPromise = runTour(longStep);
    // Kick off second tour immediately — it should mark the first as cancelled.
    const second = await runTour([{ selector: "#a", message: "second", duration_ms: 1 }]);
    const first = await firstPromise;
    expect(first.cancelled).toBe(true);
    expect(second.cancelled).toBe(false);
  });

  it("uses custom selector resolver when provided", async () => {
    const sentinel = document.createElement("div");
    document.body.appendChild(sentinel);
    const resolver = vi.fn().mockReturnValue(sentinel);
    const steps: TourStep[] = [{ selector: "wiii://step-1", message: "x", duration_ms: 1 }];
    const result = await runTour(steps, { resolveSelector: resolver });
    expect(resolver).toHaveBeenCalledWith("wiii://step-1");
    expect(result.completed_steps).toBe(1);
  });
});
