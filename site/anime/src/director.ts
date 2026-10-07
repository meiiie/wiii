import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { Sfx } from "./audio";
import { StageFX, type HitMode } from "./fx";
import { InkField } from "./gl";

gsap.registerPlugin(ScrollTrigger);

type ActId = "spark" | "title" | "work" | "neko" | "kakoi" | "still" | "credits";
type Pt = { x: number; y: number };
type Cubic = [Pt, Pt, Pt, Pt];
type Passage = "action" | "fluid";
type SfxKind = "flight" | "wrap" | "impact" | "slash" | "quiet" | "open" | "tick" | "whoosh" | "sub";

type Act = {
  id: ActId;
  el: HTMLElement;
  pin: HTMLElement;
  label: string;
  p: number;
  prev: number;
  active: boolean;
};

type Beat = {
  act: ActId;
  at: number;
  glyph: string;
  rot: number;
  mode: HitMode;
  sfx: SfxKind;
};

type Mark = { x: number; y: number; a: number };
type Dust = { x: number; y: number; vx: number; vy: number; life: number };

const FLIGHT: Cubic[] = [
  [
    { x: 50, y: 58 },
    { x: 74, y: 56 },
    { x: 86, y: 32 },
    { x: 72, y: 20 },
  ],
  [
    { x: 72, y: 20 },
    { x: 56, y: 6 },
    { x: 28, y: 16 },
    { x: 26, y: 42 },
  ],
  [
    { x: 26, y: 42 },
    { x: 24, y: 60 },
    { x: 46, y: 70 },
    { x: 58, y: 52 },
  ],
];

const BEATS: Beat[] = [
  { act: "spark", at: 0.16, glyph: "シュンッ", rot: -16, mode: "micro", sfx: "whoosh" },
  { act: "spark", at: 0.36, glyph: "クルリ", rot: 9, mode: "micro", sfx: "wrap" },
  { act: "spark", at: 0.76, glyph: "トンッ", rot: -12, mode: "major", sfx: "impact" },
  { act: "title", at: 0.06, glyph: "", rot: 0, mode: "micro", sfx: "whoosh" },
  { act: "work", at: 0.12, glyph: "ズバッ", rot: -18, mode: "major", sfx: "slash" },
  { act: "work", at: 0.28, glyph: "ズバッ", rot: 11, mode: "micro", sfx: "slash" },
  { act: "work", at: 0.44, glyph: "ズバッ", rot: -8, mode: "micro", sfx: "slash" },
  { act: "work", at: 0.6, glyph: "シーン", rot: 0, mode: "quiet", sfx: "quiet" },
  { act: "neko", at: 0.08, glyph: "シュンッ", rot: -22, mode: "micro", sfx: "whoosh" },
  { act: "neko", at: 0.42, glyph: "トンッ", rot: 6, mode: "micro", sfx: "impact" },
  { act: "neko", at: 0.56, glyph: "クルリ", rot: 8, mode: "micro", sfx: "tick" },
  { act: "neko", at: 0.68, glyph: "ピタッ", rot: -4, mode: "micro", sfx: "tick" },
  { act: "neko", at: 0.8, glyph: "トンッ", rot: 5, mode: "micro", sfx: "tick" },
  { act: "kakoi", at: 0.06, glyph: "ワァッ", rot: -7, mode: "micro", sfx: "open" },
  { act: "kakoi", at: 0.5, glyph: "", rot: 0, mode: "micro", sfx: "impact" },
  { act: "kakoi", at: 0.62, glyph: "", rot: 0, mode: "micro", sfx: "impact" },
  { act: "kakoi", at: 0.74, glyph: "", rot: 0, mode: "micro", sfx: "impact" },
  { act: "kakoi", at: 0.84, glyph: "", rot: 0, mode: "micro", sfx: "impact" },
  { act: "kakoi", at: 0.92, glyph: "", rot: 0, mode: "micro", sfx: "impact" },
  { act: "kakoi", at: 0.97, glyph: "囲", rot: 0, mode: "major", sfx: "sub" },
  { act: "still", at: 0.74, glyph: "ピタッ", rot: 4, mode: "quiet", sfx: "tick" },
];

const RULE_AT = [0.5, 0.62, 0.74, 0.84, 0.92];
const DEBRIS = [
  { l: "1.6%", t: "14%", r: -3 },
  { l: "82%", t: "12%", r: 3 },
  { l: "1.6%", t: "42%", r: 2 },
  { l: "80%", t: "68%", r: -2 },
];
const POSE_LINE: Record<string, string> = {
  peek: "Peek. Present, listening, ready.",
  mochi: "Mochi. Comfortable, complete, available.",
  nap: "Nap. Resting, without disappearing.",
  tilt: "Tilt. Curious, checking, needs attention.",
};

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ramp = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const onTwos = (t: number, steps: number) => Math.floor(clamp01(t) * steps) / steps;
const easeInOut = (t: number) => {
  const x = clamp01(t);
  return x < 0.5 ? 4 * x * x * x : 1 - ((-2 * x + 2) ** 3) / 2;
};

function cubic(c: Cubic, t: number): Pt {
  const [p0, p1, p2, p3] = c;
  const u = 1 - t;
  return {
    x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
    y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
  };
}

function flightPoint(t: number): Pt {
  const x = clamp01(t) * FLIGHT.length;
  const i = Math.min(FLIGHT.length - 1, Math.floor(x));
  return cubic(FLIGHT[i], x - i);
}

function along(points: Pt[], t: number): Pt {
  if (points.length === 1) return points[0];
  const x = clamp01(t) * (points.length - 1);
  const i = Math.min(points.length - 2, Math.floor(x));
  const local = x - i;
  return {
    x: lerp(points[i].x, points[i + 1].x, local),
    y: lerp(points[i].y, points[i + 1].y, local),
  };
}

function quad(a: Pt, c: Pt, b: Pt, t: number): Pt {
  const u = 1 - t;
  return {
    x: u * u * a.x + 2 * u * t * c.x + t * t * b.x,
    y: u * u * a.y + 2 * u * t * c.y + t * t * b.y,
  };
}

class Spring {
  v = 0;
  constructor(
    public x: number,
    private k = 0.12,
    private d = 0.74,
  ) {}
  step(target: number): number {
    this.v = (this.v + (target - this.x) * this.k) * this.d;
    this.x += this.v;
    return this.x;
  }
}

const mobile = () => window.matchMedia("(max-width: 800px)").matches;

export async function start(): Promise<void> {
  const lenis = new Lenis({
    autoRaf: false,
    lerp: 0.085,
    smoothWheel: true,
    syncTouch: false,
    anchors: true,
    respectReducedMotion: false,
  });
  lenis.on("scroll", ScrollTrigger.update);

  const spark = document.getElementById("spark") as HTMLElement;
  const lockup = document.getElementById("lockup") as HTMLElement;
  const fold = document.getElementById("fold") as HTMLElement;
  const cue = document.getElementById("cue") as HTMLElement;
  const sheetItems = [...document.querySelectorAll<HTMLElement>("#sheet li")];
  const heroName = document.getElementById("hero-name") as HTMLElement;
  const slices = [...heroName.querySelectorAll<HTMLElement>(".slice")];
  const sweep = document.getElementById("sweep") as HTMLElement;
  const titleBlock = document.querySelector(".title-copy") as HTMLElement;
  const manga = document.getElementById("manga") as HTMLElement;
  const cuts = ["cut-a", "cut-b", "cut-c"].map((id) => document.getElementById(id) as HTMLElement);
  const freeze = document.getElementById("freeze") as HTMLElement;
  const workLayout = document.getElementById("work-layout") as HTMLElement;
  const nekoCrack = document.getElementById("neko-crack") as HTMLElement;
  const nekoFlyer = document.getElementById("neko-flyer") as HTMLElement;
  const poseLives = [...document.querySelectorAll<SVGElement>("#neko-flyer .pose-live")];
  const poseCaption = document.getElementById("pose-caption") as HTMLElement;
  const ghosts = [...document.querySelectorAll<HTMLElement>(".ghost")];
  const dustCanvas = document.getElementById("dust") as HTMLCanvasElement;
  const dustCtx = dustCanvas.getContext("2d");
  const kakoiDisc = document.getElementById("kakoi-disc") as HTMLElement;
  const rules = [...document.querySelectorAll<HTMLElement>(".rule")];
  const ringCanvas = document.getElementById("ring") as HTMLCanvasElement;
  const ringCtx = ringCanvas.getContext("2d");
  const stillArc = document.getElementById("still-arc") as HTMLElement;
  const smearSheet = document.getElementById("smear-sheet") as HTMLTemplateElement;
  for (const host of [nekoFlyer, ...ghosts]) host.prepend(smearSheet.content.cloneNode(true));
  const stillLines = [...document.querySelectorAll<HTMLElement>("#still-stack .still-line")];
  const colo = document.getElementById("colo") as HTMLElement;
  const iris = document.getElementById("iris") as HTMLElement;
  const again = document.getElementById("again") as HTMLElement;
  const endCue = document.getElementById("end-cue") as HTMLElement;
  const shock = document.getElementById("shock") as HTMLElement;
  const actLabel = document.getElementById("act-label") as HTMLElement;
  const frameLabel = document.getElementById("frame-label") as HTMLElement;
  const brandMark = document.getElementById("brand-mark") as HTMLImageElement;
  const theme = document.getElementById("theme-color") as HTMLMetaElement;
  const reelLinks = [...document.querySelectorAll<HTMLAnchorElement>(".reel a")];
  const glCanvas = document.getElementById("gl") as HTMLCanvasElement;
  const strokeCanvas = document.getElementById("stroke") as HTMLCanvasElement;
  const strokeCtx = strokeCanvas.getContext("2d");
  const moteCanvas = document.getElementById("motes") as HTMLCanvasElement;
  const moteCtx = moteCanvas.getContext("2d");
  const trailBits = [...document.querySelectorAll<HTMLElement>("#trail i")];
  const nekoPin = document.querySelector("#act-neko .act__pin") as HTMLElement;
  const shade = document.getElementById("shade") as HTMLElement;

  const ink = new InkField(glCanvas);
  const glOn = ink.mount();
  if (!glOn) glCanvas.style.display = "none";
  const fx = new StageFX(
    document.getElementById("fxc") as HTMLCanvasElement,
    document.getElementById("flash") as HTMLElement,
    shade,
    document.getElementById("glyph") as HTMLElement,
    document.getElementById("grain") as HTMLElement,
  );
  const sfx = new Sfx();
  const soundBtn = document.getElementById("sound") as HTMLButtonElement;
  soundBtn.addEventListener("click", async () => {
    const on = await sfx.toggle();
    soundBtn.setAttribute("aria-pressed", on ? "true" : "false");
    soundBtn.lastChild!.textContent = on ? " Sound on" : " Sound off";
  });

  const acts: Act[] = [
    ["spark", "01 Spark"],
    ["title", "02 Title"],
    ["work", "03 Work"],
    ["neko", "04 Neko"],
    ["kakoi", "05 Kakoi"],
    ["still", "06 Still"],
    ["credits", "07 Return"],
  ].map(([id, label]) => {
    const el = document.getElementById(`act-${id}`) as HTMLElement;
    const pin = el.querySelector(".act__pin") as HTMLElement;
    return { id: id as ActId, el, pin, label, p: 0, prev: 0, active: false };
  });

  for (const act of acts) {
    ScrollTrigger.create({
      trigger: act.el,
      start: "top top",
      end: "bottom bottom",
      pin: act.pin,
      pinSpacing: false,
      anticipatePin: 1,
      onToggle: (self) => {
        act.active = self.isActive;
      },
      onUpdate: (self) => {
        act.p = self.progress;
      },
    });
  }

  const springX = new Spring(window.innerWidth * 0.5);
  const springY = new Spring(window.innerHeight * 0.48);
  let target: Pt = { x: springX.x, y: springY.x };
  let shown = acts[0];
  let passage: Passage = "fluid";
  let lastPassage: Passage = "fluid";
  let shockAmt = 0;
  let shockScale = 0;
  let stillAmt = 0;
  let radialAmt = 0;
  let heldFrame: number | null = null;
  let shakeFrames = [8, -5, 3, -1, 0];
  let shakeEvery = 48;
  let shakeStep = -1;
  let shakeClock = 0;
  let stepBucket = -1;
  const trail: Mark[] = [];
  const queued: { beat: Beat; at: number }[] = [];
  let poseNow = "peek";
  let dust: Dust[] = [];
  let dustClock = 0;
  let dustLive = false;
  let impactDrawn = false;
  const specks = Array.from({ length: 20 }, () => ({
    x: Math.random(),
    y: Math.random(),
    s: 5 + Math.random() * 11,
    v: 0.006 + Math.random() * 0.012,
    phase: Math.random() * Math.PI * 2,
    squash: 0.35 + Math.random() * 1.3,
  }));

  const resizeCanvases = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    for (const canvas of [strokeCanvas, dustCanvas, moteCanvas, ringCanvas]) {
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
    }
    strokeCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    dustCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    moteCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    ringCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const resize = () => {
    ink.resize();
    fx.resize();
    resizeCanvases();
    ScrollTrigger.refresh();
  };
  resize();
  window.addEventListener("resize", resize);

  const started = performance.now();

  const drawStroke = (p: number) => {
    if (!strokeCtx) return;
    const w = window.innerWidth;
    const h = window.innerHeight;
    strokeCtx.clearRect(0, 0, w, h);
    const travel = onTwos(ramp(p, 0.08, 0.5), 8);
    if (travel <= 0.001) return;
    const steps = 64;
    const n = Math.max(2, Math.floor(steps * travel));
    strokeCtx.lineCap = "round";
    strokeCtx.strokeStyle = "rgba(245,240,230,0.94)";
    for (let i = 1; i <= n; i++) {
      const a = flightPoint((i - 1) / steps);
      const b = flightPoint(i / steps);
      const thick = 1.6 + Math.sin((i / steps) * Math.PI) * (i / steps > 0.45 ? 18 : 5);
      strokeCtx.beginPath();
      strokeCtx.moveTo((a.x / 100) * w, (a.y / 100) * h);
      strokeCtx.lineTo((b.x / 100) * w, (b.y / 100) * h);
      strokeCtx.lineWidth = thick;
      strokeCtx.stroke();
    }
  };

  const ringRadius = () => Math.min(window.innerWidth, window.innerHeight) * (mobile() ? 0.47 : 0.46);

  const drawRing = (amount: number) => {
    if (!ringCtx) return;
    const w = window.innerWidth;
    const h = window.innerHeight;
    ringCtx.clearRect(0, 0, w, h);
    if (amount <= 0.001) return;
    const cx = w * 0.5;
    const cy = h * 0.5;
    const radius = ringRadius();
    const steps = 100;
    const n = Math.max(2, Math.floor(steps * amount));
    ringCtx.lineCap = "round";
    for (let i = 1; i <= n; i++) {
      const u = i / steps;
      if (u > 0.86 && i % 4 === 0) continue;
      const a0 = -Math.PI / 2 + ((i - 1) / steps) * Math.PI * 2;
      const a1 = -Math.PI / 2 + (i / steps) * Math.PI * 2;
      const width = u > 0.74 ? lerp(28, 1.4, (u - 0.74) / 0.26) : 8 + Math.sin(u * Math.PI) * 18;
      ringCtx.strokeStyle = u > 0.9 ? "rgba(245,240,230,0.45)" : "rgba(245,240,230,0.96)";
      ringCtx.lineWidth = width;
      ringCtx.beginPath();
      ringCtx.moveTo(cx + Math.cos(a0) * radius, cy + Math.sin(a0) * radius);
      ringCtx.lineTo(cx + Math.cos(a1) * radius, cy + Math.sin(a1) * radius);
      ringCtx.stroke();
    }
  };

  const ringTip = (amount: number): Pt => {
    const radius = ringRadius();
    const a = -Math.PI / 2 + clamp01(amount) * Math.PI * 2;
    return {
      x: window.innerWidth * 0.5 + Math.cos(a) * radius,
      y: window.innerHeight * 0.5 + Math.sin(a) * radius,
    };
  };

  const placeFlyer = (el: HTMLElement, pt: Pt, alpha: number) => {
    el.style.opacity = String(alpha);
    el.style.transform = `translate(${pt.x}px, ${pt.y}px) translate(-50%, -50%)`;
  };

  const showSmear = (host: HTMLElement, frame: number | null) => {
    host.querySelectorAll<SVGElement>(".smear").forEach((el) => {
      el.toggleAttribute("hidden", frame === null || el.dataset.smear !== String(frame));
    });
  };

  const render: Record<ActId, (p: number) => void> = {
    spark(p) {
      passage = p < 0.08 || p > 0.9 ? "fluid" : "action";
      const cues: [number, string][] = [
        [0, "0.00 — spark at rest"],
        [0.08, "1.25 — flight traces the tail"],
        [0.3, "2.50 — the fold wraps"],
        [0.5, "3.58 — the mark"],
        [0.7, "5.35 — impact"],
        [0.8, "5.75 — shockwave"],
      ];
      let label = cues[0][1];
      for (const [at, text] of cues) if (p >= at) label = text;
      if (cue.textContent !== label) cue.textContent = label;
      for (const li of sheetItems) {
        const from = Number(li.dataset.from ?? 0);
        const next = sheetItems
          .map((item) => Number(item.dataset.from ?? 0))
          .filter((n) => n > from)
          .sort((a, b) => a - b)[0];
        li.classList.toggle("on", p >= from && (next === undefined || p < next));
      }
      const folded = p >= 0.32 && p < 0.5;
      fold.style.opacity = folded ? "1" : "0";
      const foldStep = onTwos(ramp(p, 0.32, 0.48), 3);
      fold.style.transform = `translate(-50%, -50%) scale(${0.62 + foldStep * 0.38})`;
      lockup.style.opacity = p >= 0.5 ? "1" : "0";
      lockup.classList.toggle("is-smear", p >= 0.7 && p < 0.8);
      const end = flightPx(1);
      const dot = pointOf(lockup.querySelector(".lockup__name") as HTMLElement, 0.98, 0.2);
      const flightT = onTwos(ramp(p, 0.08, 0.5), 8);
      if (p < 0.08) target = flightPx(0);
      else if (p < 0.5) target = flightPx(flightT);
      else if (p < 0.7) target = end;
      else target = mix(end, dot, onTwos(ramp(p, 0.7, 0.8), 3));
      shockAmt = p >= 0.8 ? 1 : 0;
      shockScale = onTwos(ramp(p, 0.8, 1), 4) * 0.9;
      stillAmt = 0;
      radialAmt = p >= 0.8 ? 0.85 : 0;
      setBlade(0, 20, -16);
      glCanvas.style.opacity = "1";
      drawStroke(p);
    },
    title(p) {
      passage = p < 0.32 || p > 0.82 ? "action" : "fluid";
      clearStroke();
      const sweepT = onTwos(ramp(p, 0.02, 0.36), 4);
      sweep.style.opacity = sweepT > 0 && sweepT < 1 ? "1" : "0";
      sweep.style.transform = `translateX(${lerp(-46, 130, sweepT)}vw) skewX(-16deg)`;
      const keys = [-40, 26, -18, 34];
      if (p < 0.34) {
        const s = onTwos(ramp(p, 0.04, 0.32), 3);
        slices.forEach((el, i) => {
          el.style.transform = `translateY(${(1 - s) * keys[i]}px)`;
        });
      } else if (p > 0.84) {
        const s = onTwos(ramp(p, 0.84, 1), 3);
        slices.forEach((el, i) => {
          el.style.transform = `translate(${(i - 1.5) * s * 36}px, ${s * (i % 2 ? 16 : -12)}px)`;
        });
      } else {
        slices.forEach((el) => {
          el.style.transform = "none";
        });
      }
      titleBlock.style.opacity = p > 0.9 ? "0" : "1";
      const dot = pointOf(slices[3] ?? heroName, 0.7, 0.12);
      const exit = { x: window.innerWidth * 0.12, y: window.innerHeight * 0.34 };
      target = p > 0.84 ? mix(dot, exit, onTwos(ramp(p, 0.84, 1), 3)) : dot;
      shockAmt = p < 0.2 ? 1 : 0;
      shockScale = p < 0.28 ? 1.15 : 0;
      const b = onTwos(ramp(p, 0.86, 1), 3);
      setBlade(b, lerp(40, -12, b), -18);
      stillAmt = 0;
      radialAmt = 0;
      glCanvas.style.opacity = "1";
    },
    work(p) {
      const whole = p < 0.14;
      const frozen = p >= 0.58 && p < 0.9;
      passage = frozen || p > 0.9 ? "fluid" : "action";
      clearStroke();
      manga.classList.toggle("is-whole", whole);
      if (whole) {
        manga.classList.remove("is-a", "is-b", "is-c");
        cuts.forEach((cut) => cut.classList.add("is-in"));
      } else {
        const gates = [0.14, 0.28, 0.44];
        manga.classList.toggle("is-a", p >= gates[0]);
        manga.classList.toggle("is-b", p >= gates[1]);
        manga.classList.toggle("is-c", p >= gates[2]);
        cuts.forEach((cut, i) => {
          const show = mobile()
            ? p >= gates[i] && p < (i === cuts.length - 1 ? 0.58 : gates[i + 1])
            : p >= gates[i] && p < 0.58;
          cut.classList.toggle("is-in", show);
        });
      }
      freeze.classList.toggle("is-in", frozen);
      workLayout.classList.toggle("is-hold", frozen);
      if (p < 0.14) setBlade(1, lerp(18, -36, ramp(p, 0, 0.14)), -18);
      else if (p > 0.9) setBlade(onTwos(ramp(p, 0.9, 1), 3), lerp(48, -8, ramp(p, 0.9, 1)), -8);
      else setBlade(0, 0, 0);
      shockAmt = 0;
      stillAmt = frozen ? 0.35 : 0;
      radialAmt = 0;
      glCanvas.style.opacity = "1";
      target = workPoint(frozen ? 0.72 : p);
    },
    neko(p) {
      passage = p < 0.46 ? "action" : "fluid";
      clearStroke();
      nekoPin.style.clipPath = "none";
      nekoCrack.classList.toggle("is-on", p < 0.16);
      if (p < 0.12) setBlade(1 - ramp(p, 0, 0.12), lerp(10, -48, ramp(p, 0, 0.12)), -8);
      else setBlade(0, 0, 0);
      const w = window.innerWidth;
      const h = window.innerHeight;
      const from = { x: w * (mobile() ? -0.12 : -0.08), y: h * 0.62 };
      const ctrl = { x: w * 0.78, y: h * 0.08 };
      const land = { x: w * 0.5, y: h * 0.42 };
      const t = onTwos(ramp(p, 0.08, 0.42), 7);
      const flying = p >= 0.08 && t < 1;
      const pos = p < 0.08 ? from : flying ? quad(from, ctrl, land, t) : land;
      nekoFlyer.classList.toggle("is-live", p >= 0.08);
      placeFlyer(nekoFlyer, pos, p >= 0.08 ? 1 : 0);
      const frame = flying ? Math.floor(t * 3) % 3 : null;
      showSmear(nekoFlyer, frame);
      if (frame !== null) {
        for (const live of poseLives) live.setAttribute("hidden", "");
      }
      ghosts.forEach((ghost, i) => {
        const gt = t - (i + 1) / 7;
        if (!flying || gt <= 0) {
          ghost.style.opacity = "0";
          showSmear(ghost, null);
          return;
        }
        placeFlyer(ghost, quad(from, ctrl, land, Math.max(0, gt)), 0.36 - i * 0.1);
        showSmear(ghost, Math.floor(gt * 3) % 3);
      });
      let pose = "peek";
      if (p >= 0.8) pose = "tilt";
      else if (p >= 0.68) pose = "nap";
      else if (p >= 0.56) pose = "mochi";
      if (p >= 0.42 && pose !== poseNow) {
        poseNow = pose;
        nekoFlyer.classList.add("is-squash");
        window.setTimeout(() => nekoFlyer.classList.remove("is-squash"), 120);
      }
      if (frame === null && p >= 0.42) {
        for (const live of poseLives) {
          if (live.dataset.pose === pose) live.removeAttribute("hidden");
          else live.setAttribute("hidden", "");
        }
        const line = POSE_LINE[pose];
        if (poseCaption.textContent !== line) poseCaption.textContent = line;
        poseCaption.style.opacity = "1";
      } else {
        poseCaption.style.opacity = "0";
      }
      if (p >= 0.42 && !dustLive) {
        dustLive = true;
        dust = Array.from({ length: 16 }, (_, i) => {
          const a = Math.PI + (i / 16) * Math.PI;
          return {
            x: land.x,
            y: land.y + 80,
            vx: Math.cos(a) * (1.4 + (i % 4)),
            vy: -0.4 - (i % 3) * 0.3,
            life: 1,
          };
        });
      }
      if (p < 0.3) dustLive = false;
      target = p < 0.46 ? pos : { x: land.x, y: land.y - Math.min(120, h * 0.16) };
      shockAmt = 0;
      stillAmt = 0;
      radialAmt = 0;
      glCanvas.style.opacity = "0";
    },
    kakoi(p) {
      const grow = onTwos(ramp(p, 0.05, 0.42), 16);
      passage = p < 0.92 ? "action" : "fluid";
      clearStroke();
      drawRing(grow);
      setBlade(0, 0, 0);
      nekoPin.style.clipPath = "none";
      const open = grow >= 0.94;
      const diameter = ringRadius() * 2;
      kakoiDisc.style.width = `${diameter}px`;
      kakoiDisc.style.height = `${diameter}px`;
      kakoiDisc.style.opacity = open ? "1" : "0";
      kakoiDisc.style.transform = "translate(-50%, -50%)";
      let idx = -1;
      for (let i = 0; i < RULE_AT.length; i++) if (p >= RULE_AT[i]) idx = i;
      const phone = mobile();
      rules.forEach((rule, i) => {
        rule.classList.remove("is-now", "is-debris");
        rule.style.left = "";
        rule.style.top = "";
        rule.style.transform = "";
        if (i === idx) rule.classList.add("is-now");
        else if (i < idx && !phone) {
          const spot = DEBRIS[i] ?? DEBRIS[DEBRIS.length - 1];
          rule.classList.add("is-debris");
          rule.style.left = spot.l;
          rule.style.top = spot.t;
          rule.style.transform = `rotate(${spot.r}deg)`;
        }
      });
      const radius = ringRadius();
      let aim = ringTip(grow);
      if (idx >= 0) {
        aim = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5 - radius + 22 };
      }
      target = aim;
      shockAmt = 0;
      stillAmt = p >= 0.92 ? 0.45 : 0;
      radialAmt = 0;
      glCanvas.style.opacity = "1";
    },
    still(p) {
      passage = "fluid";
      clearStroke();
      setBlade(0, 0, 0);
      nekoPin.style.clipPath = "none";
      stillArc.classList.toggle("is-on", p < 0.18);
      const cutsAt = [0, 0.74, 0.84];
      let lineOn = 0;
      for (let i = 0; i < cutsAt.length; i++) if (p >= cutsAt[i]) lineOn = i;
      stillLines.forEach((line, i) => {
        line.style.opacity = i === lineOn ? "1" : "0";
        line.style.transform = "none";
      });
      target = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.42 };
      shockAmt = 0;
      stillAmt = 1;
      radialAmt = 0;
      glCanvas.style.opacity = "0";
    },
    credits(p) {
      passage = "fluid";
      clearStroke();
      setBlade(0, 0, 0);
      colo.style.opacity = p >= 0.42 ? "0" : "1";
      const irisP = easeInOut(ramp(p, 0.38, 0.8));
      iris.style.transform = `translate(-50%, -50%) scale(${irisP})`;
      again.style.opacity = p >= 0.78 ? "1" : "0";
      endCue.style.opacity = p >= 0.82 ? "1" : "0";
      const from = { x: window.innerWidth * 0.18, y: window.innerHeight * 0.42 };
      target = mix(from, flightPx(0), easeInOut(ramp(p, 0.34, 0.78)));
      shockAmt = 0;
      stillAmt = 0;
      radialAmt = 0;
      glCanvas.style.opacity = p >= 0.5 ? "1" : "0";
    },
  };

  const punch = (kind: HitMode) => {
    if (kind === "quiet") return;
    shakeStep = 0;
    shakeClock = performance.now();
    if (kind === "major") {
      shakeFrames = [20, 20, -15, -15, 10, 10, -6, -6, 3, -2, 0];
      shakeEvery = 70;
      document.documentElement.classList.add("is-hit");
      window.setTimeout(() => document.documentElement.classList.remove("is-hit"), 420);
    } else {
      shakeFrames = [9, -6, 4, -2, 0];
      shakeEvery = 50;
    }
  };

  const fire = (beat: Beat, x: number, y: number) => {
    const resolved = fx.strike(x, y, beat.glyph, beat.rot, beat.mode);
    sfx.play(beat.sfx);
    punch(resolved);
  };

  const drawMotes = (now: number) => {
    if (!moteCtx) return;
    moteCtx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    const paper = document.documentElement.classList.contains("on-paper");
    moteCtx.fillStyle = paper ? "#2A2928" : "#F5F0E6";
    const t = now / 1000;
    for (const speck of specks) {
      const y = (speck.y + t * speck.v) % 1;
      moteCtx.globalAlpha = 0.45 + 0.35 * Math.sin(t * 0.6 + speck.phase);
      moteCtx.fillRect(
        speck.x * window.innerWidth,
        y * window.innerHeight,
        speck.s * speck.squash,
        speck.s,
      );
    }
    moteCtx.globalAlpha = 1;
  };

  const drawDust = (now: number, active: boolean) => {
    if (!dustCtx) return;
    dustCtx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    if (!active) return;
    if (now - dustClock > 80) {
      dustClock = now;
      for (const bit of dust) {
        bit.x += bit.vx * 4;
        bit.y += bit.vy * 4;
        bit.vy += 0.35;
        bit.life -= 0.14;
      }
    }
    dustCtx.fillStyle = "#2A2928";
    for (const bit of dust) {
      if (bit.life <= 0) continue;
      dustCtx.globalAlpha = bit.life;
      dustCtx.fillRect(bit.x, bit.y, 4, 2);
    }
    dustCtx.globalAlpha = 1;
  };

  const draw = (now: number) => {
    const live = acts.filter((item) => item.active);
    if (live.length) shown = live[live.length - 1];
    else {
      const y = window.scrollY + 8;
      for (const item of acts) if (item.el.offsetTop <= y) shown = item;
    }
    const act = shown;
    const prev = act.prev;
    render[act.id](act.p);
    target = {
      x: Math.min(window.innerWidth - 12, Math.max(12, target.x)),
      y: Math.min(window.innerHeight - 12, Math.max(12, target.y)),
    };

    let x: number;
    let y: number;
    if (passage === "fluid") {
      if (lastPassage === "action") {
        springX.v = 0;
        springY.v = 0;
      }
      x = springX.step(target.x);
      y = springY.step(target.y);
    } else {
      const bucket = Math.floor(now / 83);
      if (bucket !== stepBucket) {
        stepBucket = bucket;
        const dx = target.x - springX.x;
        const dy = target.y - springY.x;
        const a = Math.atan2(dy, dx);
        springX.v = dx;
        springY.v = dy;
        springX.x = target.x;
        springY.x = target.y;
        trail.unshift({ x: target.x, y: target.y, a });
        if (trail.length > 4) trail.pop();
      }
      x = springX.x;
      y = springY.x;
    }
    lastPassage = passage;

    if (act.p > prev && act.p - prev < 0.18) {
      for (const beat of BEATS) {
        if (beat.act !== act.id) continue;
        if (prev < beat.at && act.p >= beat.at) {
          if (beat.mode === "major") {
            document.documentElement.classList.add("is-wind");
            queued.push({ beat, at: now + 150 });
          } else fire(beat, x, y);
        }
      }
    }
    for (let i = queued.length - 1; i >= 0; i--) {
      if (now >= queued[i].at) {
        document.documentElement.classList.remove("is-wind");
        fire(queued[i].beat, springX.x, springY.x);
        queued.splice(i, 1);
      }
    }
    act.prev = act.p;

    const speed = Math.hypot(springX.v, springY.v);
    const smearing = passage === "action" && speed > 28;
    const angle = Math.atan2(springY.v, springX.v);
    spark.classList.toggle("is-smear", smearing);
    spark.style.transform = `translate(${x}px, ${y}px) rotate(${smearing ? angle : 0}rad)`;
    trailBits.forEach((bit, i) => {
      const prevMark = trail[i + 1];
      if (!smearing || !prevMark) {
        bit.style.opacity = "0";
        return;
      }
      bit.style.opacity = String(0.45 - i * 0.12);
      bit.style.transform = `translate(${prevMark.x}px, ${prevMark.y}px) rotate(${prevMark.a}rad)`;
    });

    const paperChrome =
      act.id === "neko" || act.id === "still" || (act.id === "credits" && act.p < 0.55);
    const paperSpark = paperChrome || (act.id === "kakoi" && act.p > 0.42);
    spark.classList.toggle("on-paper", paperSpark);
    document.documentElement.classList.toggle("on-paper", paperChrome);
    const nextMark = paperChrome ? "/brand/neko-peek-mark.svg" : "/brand/neko-peek-mark-on-dark.svg";
    if (!brandMark.src.endsWith(nextMark)) brandMark.src = nextMark;
    theme.content = paperChrome ? "#F3EEE4" : "#07080C";

    if (act.id === "still") {
      const breath = 0.55 + 0.45 * (0.5 + 0.5 * Math.sin(now * 0.0008));
      spark.style.opacity = String(breath);
      drawMotes(now);
    } else {
      spark.style.opacity = "1";
      moteCtx?.clearRect(0, 0, window.innerWidth, window.innerHeight);
    }

    shock.style.opacity = shockAmt > 0 ? "1" : "0";
    shock.style.transform = `translate(${x}px, ${y}px) scale(${0.2 + shockScale})`;

    if (!fx.holding) {
      const dim = act.id === "kakoi" && act.p < 0.4 ? ramp(act.p, 0.02, 0.16) * 0.55 : 0;
      shade.style.opacity = String(dim);
    }

    if (shakeStep >= 0) {
      if (now - shakeClock > shakeEvery) {
        shakeClock = now;
        shakeStep += 1;
      }
      const mag = shakeFrames[Math.min(shakeStep, shakeFrames.length - 1)] ?? 0;
      document.querySelectorAll<HTMLElement>(".act__shake").forEach((el) => {
        el.style.translate = `${mag}px ${mag * -0.4}px`;
      });
      if (shakeStep >= shakeFrames.length) shakeStep = -1;
    }

    const scrollMax = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const globalP = lenis.animatedScroll / scrollMax;
    const vel = Math.min(1, Math.abs(lenis.velocity) / 1400);
    const quietPicture =
      act.id === "still" ||
      (act.id === "work" && act.p >= 0.58 && act.p < 0.9) ||
      (act.id === "kakoi" && act.p > 0.91);
    const flying = act.id === "spark" && act.p > 0.08 && act.p < 0.5;
    const impactWindow = radialAmt > 0.02;
    if (!impactWindow) impactDrawn = false;
    if (!fx.holding) {
      if (impactWindow) {
        if (!impactDrawn) {
          fx.clear();
          fx.radial(x, y, radialAmt);
          impactDrawn = true;
        }
      } else if (vel < 0.08 && !flying) {
        fx.clear();
      } else {
        fx.fade();
        if (!quietPicture && (flying || (vel > 0.18 && passage === "action"))) {
          fx.streaks(flying ? 0.55 : vel);
        }
      }
    }
    drawDust(now, act.id === "neko" && dustLive);

    if (glOn) {
      ink.draw({
        time: (now - started) / 1000,
        scroll: globalP,
        vel,
        impact: document.documentElement.classList.contains("is-hit") ? 0.85 : shockAmt * 0.25,
        sparkX: x / window.innerWidth,
        sparkY: y / window.innerHeight,
        still: stillAmt,
      });
    }

    actLabel.textContent = act.label;
    const climbing = !quietPicture;
    if (climbing) heldFrame = null;
    const frame = heldFrame ?? Math.round(globalP * 2400 + 1);
    if (!climbing && heldFrame === null) heldFrame = frame;
    frameLabel.textContent = `F ${String(frame).padStart(4, "0")}`;
    for (const link of reelLinks) {
      link.setAttribute("aria-current", link.getAttribute("href") === `#act-${act.id}` ? "true" : "false");
    }
  };

  gsap.ticker.lagSmoothing(0);
  gsap.ticker.add((time) => {
    lenis.raf(time * 1000);
    draw(performance.now());
  });

  await document.fonts.ready;
  resize();

  window.__WIII = {
    lenis,
    scrollToAct(id: string, progress: number) {
      const el = document.getElementById(id);
      if (!el) return;
      const top = el.getBoundingClientRect().top + window.scrollY;
      const span = Math.max(0, el.offsetHeight - window.innerHeight);
      lenis.scrollTo(top + span * clamp01(progress), { immediate: true, force: true });
      ScrollTrigger.update();
    },
  };
}

function pointOf(el: HTMLElement, xBias: number, yBias: number): Pt {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width * xBias, y: r.top + r.height * yBias };
}

function flightPx(t: number): Pt {
  const p = flightPoint(t);
  return { x: (p.x / 100) * window.innerWidth, y: (p.y / 100) * window.innerHeight };
}

function mix(a: Pt, b: Pt, t: number): Pt {
  return { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) };
}

function clearStroke(): void {
  const canvas = document.getElementById("stroke") as HTMLCanvasElement | null;
  const ctx = canvas?.getContext("2d");
  if (!ctx || !canvas) return;
  ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
}

function setBlade(opacity: number, shiftVw: number, rot: number): void {
  const blade = document.getElementById("blade");
  if (!blade) return;
  blade.style.opacity = String(opacity);
  blade.style.transform = `translateX(${shiftVw}vw) rotate(${rot}deg)`;
}

function workPoint(p: number): Pt {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const pts = mobile()
    ? [
        { x: w * 0.12, y: h * 0.38 },
        { x: w * 0.86, y: h * 0.46 },
        { x: w * 0.16, y: h * 0.58 },
        { x: w * 0.84, y: h * 0.66 },
        { x: w * 0.5, y: h * 0.48 },
      ]
    : [
        { x: w * 0.14, y: h * 0.32 },
        { x: w * 0.48, y: h * 0.24 },
        { x: w * 0.62, y: h * 0.34 },
        { x: w * 0.9, y: h * 0.3 },
        { x: w * 0.22, y: h * 0.7 },
        { x: w * 0.62, y: h * 0.74 },
        { x: w * 0.5, y: h * 0.52 },
      ];
  return along(pts, onTwos(p, 8));
}

declare global {
  interface Window {
    __WIII?: {
      lenis: Lenis;
      scrollToAct: (id: string, progress: number) => void;
    };
  }
}
