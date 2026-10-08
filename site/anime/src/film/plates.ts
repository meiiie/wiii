/** Plate sets, focal points, and camera keys. y grows downward, matching the keyframes. */

export type ActId = "awaken" | "intrusion" | "clash" | "observe" | "neko" | "kakoi" | "still" | "return";
export type PlateId = ActId | "impact";
export type Orient = "landscape" | "portrait";
export type Tier = "1280" | "1920" | "2560";

/** Portrait when the viewport is taller than 4:3. */
export const PORTRAIT_AT = 0.75;

export const ACTS: ActId[] = ["awaken", "intrusion", "clash", "observe", "neko", "kakoi", "still", "return"];

export const FILES: Record<PlateId, string> = {
  awaken: "kf01_awaken",
  intrusion: "kf02_intrusion",
  clash: "kf03_clash",
  impact: "kf04_impact",
  observe: "kf05_observe",
  neko: "kf06_neko_burst",
  kakoi: "kf07_kakoi",
  still: "kf08_still",
  return: "kf01_awaken",
};

/**
 * Portrait focals from the plate README. y grows downward.
 * kf01 is the eye at (0.58, 0.56). kf03 and kf04 share the contact point.
 */
export const PORTRAIT_FOCAL: Record<PlateId, { x: number; y: number }> = {
  awaken: { x: 0.58, y: 0.56 },
  intrusion: { x: 0.5, y: 0.34 },
  clash: { x: 0.5, y: 0.47 },
  impact: { x: 0.5, y: 0.47 },
  observe: { x: 0.5, y: 0.62 },
  neko: { x: 0.5, y: 0.4 },
  kakoi: { x: 0.5, y: 0.45 },
  still: { x: 0.5, y: 0.68 },
  return: { x: 0.58, y: 0.56 },
};

export type CamKey = {
  zoom: [number, number];
  dolly: [number, number];
  truck: [[number, number], [number, number]];
  roll: [number, number];
  focus: [number, number];
  center: [[number, number], [number, number]];
  /** Crop anchor. y grows downward. */
  focal: { x: number; y: number };
};

const L = (
  zoom: [number, number],
  dolly: [number, number],
  truck: [[number, number], [number, number]],
  roll: [number, number],
  focus: [number, number],
  center: [[number, number], [number, number]],
  focal: { x: number; y: number },
): CamKey => ({ zoom, dolly, truck, roll, focus, center, focal });

export const LANDSCAPE: Record<ActId, CamKey> = {
  awaken: L([1.05, 1.22], [0, 0.18], [[0.02, 0], [-0.03, 0.01]], [0, -0.012], [0.45, 0.62], [[0.48, 0.42], [0.42, 0.38]], { x: 0.42, y: 0.38 }),
  intrusion: L([1.04, 1.16], [0.02, 0.2], [[0.04, 0.01], [-0.05, -0.02]], [0.01, -0.016], [0.4, 0.58], [[0.55, 0.48], [0.46, 0.5]], { x: 0.48, y: 0.42 }),
  clash: L([1.08, 1.16], [0.05, 0.25], [[-0.05, 0], [0.06, -0.012]], [-0.02, 0.02], [0.5, 0.55], [[0.5, 0.5], [0.5, 0.48]], { x: 0.5, y: 0.48 }),
  observe: L([1.02, 1.12], [0, 0.08], [[0.012, 0], [-0.02, 0.012]], [0, -0.008], [0.48, 0.52], [[0.62, 0.4], [0.56, 0.38]], { x: 0.62, y: 0.38 }),
  neko: L([1.06, 1.18], [0.04, 0.16], [[0.02, 0.02], [-0.03, -0.012]], [0.012, -0.01], [0.5, 0.64], [[0.55, 0.46], [0.5, 0.42]], { x: 0.54, y: 0.42 }),
  kakoi: L([1.25, 1.06], [0.2, 0.05], [[0, 0.03], [0, -0.02]], [0.02, 0], [0.4, 0.42], [[0.5, 0.55], [0.5, 0.5]], { x: 0.5, y: 0.5 }),
  still: L([1.02, 1.03], [0, 0], [[0, 0], [0, 0]], [0, 0], [0.45, 0.45], [[0.5, 0.46], [0.5, 0.46]], { x: 0.5, y: 0.46 }),
  return: L([1.2, 1.06], [0.16, 0.02], [[-0.02, 0.01], [0.012, 0]], [-0.01, 0], [0.68, 0.48], [[0.42, 0.38], [0.48, 0.44]], { x: 0.42, y: 0.4 }),
};

/**
 * Portrait framing is a cover-fit of the full 9:16 plate, plus a push no
 * stronger than 1.10. Centre stays put so heads are not cropped. Dolly and
 * truck stay small: the depth maps are relative. kf07 stays at 1.00 because
 * the 囲 kanji occupies y 0.02–0.30. The kf04 punch is applied in the engine,
 * and the contact centre does not move across that cut.
 */
const portrait = (zoom: [number, number], dolly: [number, number], truckY: number, focal: { x: number; y: number }): CamKey =>
  L(zoom, dolly, [[0, 0], [0, truckY]], [0, 0], [0.5, 0.52], [[0.5, 0.5], [0.5, 0.5]], focal);

export const PORTRAIT: Record<ActId, CamKey> = {
  awaken: portrait([1, 1.06], [0, 0.025], 0.012, PORTRAIT_FOCAL.awaken),
  intrusion: portrait([1, 1.05], [0, 0.02], -0.01, PORTRAIT_FOCAL.intrusion),
  clash: portrait([1.02, 1.06], [0, 0.03], 0.008, PORTRAIT_FOCAL.clash),
  observe: portrait([1, 1.04], [0, 0.015], 0.008, PORTRAIT_FOCAL.observe),
  neko: portrait([1, 1.06], [0, 0.02], -0.012, PORTRAIT_FOCAL.neko),
  kakoi: portrait([1, 1], [0, 0], 0, PORTRAIT_FOCAL.kakoi),
  still: portrait([1, 1.02], [0, 0], 0, PORTRAIT_FOCAL.still),
  return: portrait([1.04, 1.02], [0.02, 0], 0.008, PORTRAIT_FOCAL.return),
};

export type Cam = {
  zoom: number;
  dolly: number;
  truck: [number, number];
  roll: number;
  focus: number;
  center: [number, number];
  focal: { x: number; y: number };
};

const smooth = (t: number) => {
  const x = Math.min(1, Math.max(0, t));
  return x * x * (3 - 2 * x);
};

export function evalCam(key: CamKey, t: number, breathe: number): Cam {
  const e = smooth(t);
  const mix = (a: number, b: number) => a + (b - a) * e;
  const truck: [number, number] = [mix(key.truck[0][0], key.truck[1][0]), mix(key.truck[0][1], key.truck[1][1])];
  return {
    zoom: mix(key.zoom[0], key.zoom[1]) * (1 + breathe),
    dolly: mix(key.dolly[0], key.dolly[1]),
    truck,
    roll: mix(key.roll[0], key.roll[1]),
    focus: mix(key.focus[0], key.focus[1]),
    center: [mix(key.center[0][0], key.center[1][0]), mix(key.center[0][1], key.center[1][1])],
    focal: key.focal,
  };
}

export function plateFor(act: ActId, t: number): PlateId {
  if (act === "clash" && t >= 0.46) return "impact";
  if (act === "neko" && t < 0.42) return "observe";
  if (act === "neko") return "neko";
  if (act === "return") return "awaken";
  return act;
}

/** The single plate to warm ahead of the one on screen. */
export function aheadPlate(act: ActId, t: number): PlateId {
  if (act === "clash" && t < 0.46) return "impact";
  if (act === "neko" && t < 0.42) return "neko";
  const order = ACTS;
  const index = order.indexOf(act);
  const next = order[Math.min(order.length - 1, index + 1)];
  return plateFor(next, 0);
}

export function orientOf(w = window.innerWidth, h = window.innerHeight): Orient {
  return w / Math.max(1, h) < PORTRAIT_AT ? "portrait" : "landscape";
}

export function phoneTier(): boolean {
  return Math.min(window.innerWidth, window.innerHeight) <= 800 || window.matchMedia("(pointer: coarse)").matches;
}

/** Phones stay on 1280 or 1920. 2560 is only for a large portrait window. */
export function plateTier(orient: Orient): Tier {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const long = Math.max(window.innerWidth, window.innerHeight) * dpr;
  const phone = phoneTier();
  if (orient === "portrait") {
    if (phone) return long <= 1280 ? "1280" : "1920";
    return long >= 2400 ? "2560" : "1920";
  }
  return phone || long < 2000 ? "1920" : "2560";
}

export type PlateSource = {
  plate: string;
  fallback: string;
  depth: string;
  native: boolean;
  aspect: number;
};

export function artUrls(id: PlateId, orient: Orient): PlateSource {
  const file = FILES[id];
  const tier = plateTier(orient);
  if (orient === "portrait") {
    const depthTier = phoneTier() || tier === "1280" ? "1024" : "1920";
    return {
      plate: `/art/${file}-portrait-${tier}.avif`,
      fallback: `/art/${file}-portrait-${tier}.webp`,
      depth: `/art/depth/${file}-portrait-depth-${depthTier}.webp`,
      native: true,
      aspect: 9 / 16,
    };
  }
  return {
    plate: `/art/${file}-${tier}.webp`,
    fallback: "",
    depth: `/art/depth/${file}-depth-${tier === "2560" ? "1920" : "1024"}.webp`,
    native: false,
    aspect: 16 / 9,
  };
}

/** Portion of the plate covered by the viewport, anchored on the focal point. */
export function coverWindow(
  focal: { x: number; y: number },
  imgAspect: number,
  viewAspect: number,
): { origin: [number, number]; window: [number, number] } {
  const aspect = Math.max(0.2, viewAspect);
  if (aspect < imgAspect) {
    const winW = Math.min(1, aspect / imgAspect);
    const x = Math.min(1 - winW, Math.max(0, focal.x - winW * 0.5));
    return { origin: [x, 0], window: [winW, 1] };
  }
  const winH = Math.min(1, imgAspect / aspect);
  const y = Math.min(1 - winH, Math.max(0, focal.y - winH * 0.5));
  return { origin: [0, y], window: [1, winH] };
}
