export interface WiiiPerformanceSample {
  name: string;
  duration: number;
  startTime: number;
  entryType: "measure" | "longtask";
}

export interface WiiiHeapSnapshot {
  usedBytes: number | null;
  totalBytes: number | null;
  limitBytes: number | null;
}

const SAMPLE_LIMIT = 240;
const samples: WiiiPerformanceSample[] = [];
let observer: PerformanceObserver | null = null;
let enabledCache: boolean | null = null;

function pushSample(sample: WiiiPerformanceSample): void {
  samples.push(sample);
  if (samples.length > SAMPLE_LIMIT) {
    samples.splice(0, samples.length - SAMPLE_LIMIT);
  }
}

export function wiiiPerformanceEnabled(): boolean {
  if (enabledCache !== null) return enabledCache;
  if (typeof window === "undefined") {
    enabledCache = false;
    return false;
  }
  const queryEnabled = new URLSearchParams(window.location.search).get("perf") === "1";
  let storedEnabled = false;
  try {
    storedEnabled = window.localStorage.getItem("wiii:performance") === "1";
  } catch {
    storedEnabled = false;
  }
  enabledCache = queryEnabled || storedEnabled;
  return enabledCache;
}

export function startWiiiPerformanceTelemetry(): void {
  if (!wiiiPerformanceEnabled() || observer || typeof PerformanceObserver === "undefined") return;
  if (!PerformanceObserver.supportedEntryTypes.includes("longtask")) return;
  observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      pushSample({
        name: entry.name || "longtask",
        duration: entry.duration,
        startTime: entry.startTime,
        entryType: "longtask",
      });
    }
  });
  observer.observe({ type: "longtask", buffered: true });
}

export function markWiiiPerformance(name: string): void {
  if (!wiiiPerformanceEnabled() || typeof performance === "undefined") return;
  performance.clearMarks(name);
  performance.mark(name);
}

export function measureWiiiPerformance(name: string, startMark: string): number | null {
  if (!wiiiPerformanceEnabled() || typeof performance === "undefined") return null;
  if (performance.getEntriesByName(startMark, "mark").length === 0) return null;
  const measure = performance.measure(name, startMark);
  pushSample({
    name,
    duration: measure.duration,
    startTime: measure.startTime,
    entryType: "measure",
  });
  performance.clearMarks(startMark);
  performance.clearMeasures(name);
  return measure.duration;
}

export function readWiiiHeapSnapshot(): WiiiHeapSnapshot {
  const memory = typeof performance === "undefined"
    ? undefined
    : (performance as Performance & {
      memory?: {
        usedJSHeapSize: number;
        totalJSHeapSize: number;
        jsHeapSizeLimit: number;
      };
    }).memory;
  return {
    usedBytes: memory?.usedJSHeapSize ?? null,
    totalBytes: memory?.totalJSHeapSize ?? null,
    limitBytes: memory?.jsHeapSizeLimit ?? null,
  };
}

export function readWiiiPerformanceSamples(): readonly WiiiPerformanceSample[] {
  return samples.slice();
}

export function resetWiiiPerformanceTelemetryForTests(): void {
  observer?.disconnect();
  observer = null;
  samples.length = 0;
  enabledCache = null;
}
