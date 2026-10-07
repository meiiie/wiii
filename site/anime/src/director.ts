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
  sfx: "flight" | "wrap" | "impact" | "slash" | "quiet" | "open" | "tick";
};

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
  { act: "spark", at: 0.16, glyph: "シュンッ", rot: -16, mode: "soft", sfx: "flight" },
  { act: "spark", at: 0.36, glyph: "クルリ", rot: 9, mode: "soft", sfx: "wrap" },
  { act: "spark", at: 0.76, glyph: "トンッ", rot: -12, mode: "hit", sfx: "impact" },
  { act: "work", at: 0.18, glyph: "ズバッ", rot: -14, mode: "slash", sfx: "slash" },
  { act: "work", at: 0.68, glyph: "シーン", rot: 0, mode: "quiet", sfx: "quiet" },
  { act: "kakoi", at: 0.06, glyph: "ワァッ", rot: -7, mode: "hit", sfx: "open" },
  { act: "still", at: 0.6, glyph: "ピタッ", rot: 5, mode: "soft", sfx: "tick" },
];

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ramp = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const easeOut = (t: number) => 1 - (1 - clamp01(t)) ** 3;
const easeIn = (t: number) => clamp01(t) ** 3;
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
  const sweep = document.getElementById("sweep") as HTMLElement;
  const panels = [...document.querySelectorAll<HTMLElement>(".panel")];
  const sfxCut = document.getElementById("sfx-cut") as HTMLElement;
  const workFoot = document.getElementById("work-foot") as HTMLElement;
  const nekoIntro = document.getElementById("neko-intro") as HTMLElement;
  const nekoTrack = document.getElementById("neko-track") as HTMLElement;
  const nekoNote = document.getElementById("neko-note") as HTMLElement;
  const poseCards = [...document.querySelectorAll<HTMLElement>(".pose-card")];
  const kakoiDisc = document.getElementById("kakoi-disc") as HTMLElement;
  const kakoiMark = document.getElementById("kakoi-mark") as HTMLElement;
  const kakoiCopy = document.getElementById("kakoi-copy") as HTMLElement;
  const rules = [...document.querySelectorAll<HTMLElement>("#rules li")];
  const stillLines = [...document.querySelectorAll<HTMLElement>("#still-stack .still-line")];
  const stillNote = document.getElementById("still-note") as HTMLElement;
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
  const nekoPin = document.querySelector("#act-neko .act__pin") as HTMLElement;

  const ink = new InkField(glCanvas);
  const glOn = ink.mount();
  if (!glOn) glCanvas.style.display = "none";
  const fx = new StageFX(
    document.getElementById("fxc") as HTMLCanvasElement,
    document.getElementById("flash") as HTMLElement,
    document.getElementById("shade") as HTMLElement,
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
  let shockAmt = 0;
  let shockScale = 0;
  let stillAmt = 0;
  let radialAmt = 0;
  let heldFrame: number | null = null;
  const shakeFrames = [10, -8, 6, -4, 2, -1, 0];
  let shakeStep = -1;
  let shakeClock = 0;

  const resize = () => {
    ink.resize();
    fx.resize();
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    strokeCanvas.width = Math.floor(window.innerWidth * dpr);
    strokeCanvas.height = Math.floor(window.innerHeight * dpr);
    strokeCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
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
    const travel = easeInOut(ramp(p, 0.08, 0.5));
    if (travel <= 0.001) return;
    const steps = 72;
    const n = Math.max(2, Math.floor(steps * travel));
    strokeCtx.lineCap = "round";
    strokeCtx.strokeStyle = "rgba(245,240,230,0.92)";
    for (let i = 1; i <= n; i++) {
      const a = flightPoint((i - 1) / steps);
      const b = flightPoint(i / steps);
      const thick = 1.4 + Math.sin((i / steps) * Math.PI) * (i / steps > 0.45 ? 16 : 4);
      strokeCtx.beginPath();
      strokeCtx.moveTo((a.x / 100) * w, (a.y / 100) * h);
      strokeCtx.lineTo((b.x / 100) * w, (b.y / 100) * h);
      strokeCtx.lineWidth = thick;
      strokeCtx.stroke();
    }
    if (p > 0.68 && p < 0.82) {
      const end = flightPoint(1);
      const name = lockup.querySelector(".lockup__name") as HTMLElement;
      const dot = pointOf(name, 0.98, 0.22);
      const t = easeIn(ramp(p, 0.7, 0.8));
      strokeCtx.beginPath();
      strokeCtx.moveTo((end.x / 100) * w, (end.y / 100) * h);
      strokeCtx.lineTo(lerp((end.x / 100) * w, dot.x, t), lerp((end.y / 100) * h, dot.y, t));
      strokeCtx.lineWidth = 2;
      strokeCtx.stroke();
    }
  };

  const render: Record<ActId, (p: number) => void> = {
    spark(p) {
      const cues: [number, string][] = [
        [0, "0.00 — spark at rest"],
        [0.08, "1.25 — flight traces the tail"],
        [0.3, "2.50 — the fold wraps"],
        [0.48, "3.58 — the mark"],
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
      const foldIn = easeOut(ramp(p, 0.32, 0.46));
      const foldOut = ramp(p, 0.5, 0.66);
      fold.style.opacity = String(foldIn * (1 - foldOut));
      fold.style.transform = `translate(-50%, -50%) scale(${0.62 + foldIn * 0.4})`;
      lockup.style.opacity = String(easeOut(ramp(p, 0.5, 0.64)));
      lockup.classList.toggle("is-smear", p > 0.7 && p < 0.79);
      const end = flightPx(1);
      const dot = pointOf(lockup.querySelector(".lockup__name") as HTMLElement, 0.98, 0.2);
      if (p < 0.08) target = flightPx(0);
      else if (p < 0.5) target = flightPx(easeInOut(ramp(p, 0.08, 0.5)));
      else if (p < 0.7) target = end;
      else target = mix(end, dot, easeIn(ramp(p, 0.7, 0.8)));
      shockAmt = ramp(p, 0.8, 0.9);
      shockScale = ramp(p, 0.8, 1) * 0.85;
      stillAmt = 0;
      radialAmt = 0;
      setBlade(0, 20, -16);
      glCanvas.style.opacity = "1";
      drawStroke(p);
    },
    title(p) {
      clearStroke();
      const sweepT = easeInOut(ramp(p, 0.02, 0.32));
      sweep.style.opacity = String(sweepT > 0 && sweepT < 1 ? 0.9 : 0);
      sweep.style.transform = `translateX(${lerp(-40, 120, sweepT)}vw) skewX(-14deg)`;
      const leave = ramp(p, 0.86, 1);
      const block = document.querySelector(".title-copy") as HTMLElement;
      block.style.opacity = String(1 - leave);
      block.style.transform = `translate3d(${leave * -30}px, ${leave * -12}px, 0)`;
      const dot = pointOf(heroName, 0.97, 0.18);
      const exit = { x: window.innerWidth * 0.86, y: window.innerHeight * 0.6 };
      target = mix(dot, exit, easeIn(ramp(p, 0.84, 1)));
      shockAmt = 1 - ramp(p, 0.02, 0.28);
      shockScale = lerp(0.85, 1.6, ramp(p, 0, 0.35));
      const b = ramp(p, 0.84, 1);
      setBlade(b, lerp(36, -8, easeInOut(b)), -18);
      stillAmt = 0;
      radialAmt = 0;
      glCanvas.style.opacity = "1";
    },
    work(p) {
      clearStroke();
      const starts = [0.04, 0.2, 0.38, 0.56];
      panels.forEach((panel, i) => {
        if (mobile()) {
          const start = 0.04 + i * 0.22;
          const inn = easeOut(ramp(p, start, start + 0.1));
          const out = i === panels.length - 1 ? 0 : ramp(p, start + 0.18, start + 0.24);
          panel.style.opacity = String(inn * (1 - out));
          panel.style.clipPath = "none";
        } else {
          const e = easeOut(ramp(p, starts[i], starts[i] + 0.1));
          panel.style.opacity = "1";
          panel.style.clipPath = `inset(0 ${(1 - e) * 100}% 0 0)`;
        }
      });
      sfxCut.style.opacity = String(easeOut(ramp(p, 0.22, 0.32)));
      workFoot.style.opacity = String(easeOut(ramp(p, 0.74, 0.86)));
      if (p < 0.16) setBlade(1 - ramp(p, 0, 0.16), lerp(-8, -80, ramp(p, 0, 0.16)), -18);
      else if (p > 0.88) setBlade(ramp(p, 0.88, 1), lerp(42, -6, ramp(p, 0.88, 1)), -8);
      else setBlade(0, 0, 0);
      shockAmt = 0;
      stillAmt = ramp(p, 0.6, 0.72) * (1 - ramp(p, 0.9, 1));
      radialAmt = 0;
      glCanvas.style.opacity = "1";
      target = workPoint(p);
    },
    neko(p) {
      clearStroke();
      const open = easeOut(ramp(p, 0, 0.12));
      nekoPin.style.clipPath = open > 0.995 ? "none" : `inset(0 ${(1 - open) * 100}% 0 0)`;
      setBlade(1 - open, lerp(0, -90, open), -8);
      nekoIntro.style.opacity = String(1 - ramp(p, 0.08, 0.18));
      nekoIntro.style.transform = `translate3d(${-ramp(p, 0.08, 0.2) * 28}px, 0, 0)`;
      nekoTrack.style.opacity = String(ramp(p, 0.12, 0.22));
      if (mobile()) {
        nekoTrack.style.transform = "none";
        poseCards.forEach((card, i) => {
          const start = 0.18 + i * 0.18;
          const inn = easeOut(ramp(p, start, start + 0.08));
          const out = i === poseCards.length - 1 ? 0 : ramp(p, start + 0.14, start + 0.2);
          card.style.opacity = String(inn * (1 - out));
        });
      } else {
        const card = poseCards[0]?.getBoundingClientRect();
        const cardW = card?.width || 720;
        const gap = window.innerWidth * 0.08;
        const pad = window.innerWidth * 0.12;
        const stride = cardW + gap;
        const t = ramp(p, 0.18, 0.92);
        const last = poseCards.length - 1;
        const index = t * last;
        const i = Math.min(last - 1, Math.floor(index));
        const local = index - i;
        const hold = local < 0.18 ? 0 : local > 0.82 ? 1 : easeInOut((local - 0.18) / 0.64);
        const focus = Math.min(last, i + hold);
        const center = pad + focus * stride + cardW / 2;
        nekoTrack.style.transform = `translate3d(${-(center - window.innerWidth / 2)}px, 0, 0)`;
        poseCards.forEach((pose) => {
          pose.style.opacity = "1";
        });
      }
      nekoNote.style.opacity = String(easeOut(ramp(p, mobile() ? 0.78 : 0.62, mobile() ? 0.9 : 0.76)));
      const center = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5 };
      const ride = { x: lerp(window.innerWidth * 0.28, window.innerWidth * 0.72, p), y: window.innerHeight * 0.58 };
      target = mix(ride, center, ramp(p, 0.9, 1));
      shockAmt = 0;
      stillAmt = 0;
      radialAmt = ramp(p, 0.92, 1);
      glCanvas.style.opacity = "0";
    },
    kakoi(p) {
      clearStroke();
      setBlade(0, 0, 0);
      nekoPin.style.clipPath = "none";
      const grow = easeInOut(ramp(p, 0.05, 0.58));
      kakoiDisc.style.transform = `translate(-50%, -50%) scale(${lerp(0.1, 1.28, grow)})`;
      kakoiMark.style.opacity = String(1 - ramp(p, 0.14, 0.3));
      kakoiCopy.style.opacity = String(easeOut(ramp(p, 0.26, 0.4)));
      rules.forEach((rule, i) => {
        const start = 0.34 + i * 0.08;
        const e = easeOut(ramp(p, start, start + 0.06));
        rule.style.opacity = String(e);
        rule.style.transform = `translate3d(${(1 - e) * 22}px, 0, 0)`;
      });
      const center = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.48 };
      const aside = { x: window.innerWidth * 0.8, y: window.innerHeight * 0.18 };
      target = mix(center, aside, easeOut(ramp(p, 0.2, 0.38)));
      shockAmt = 0;
      stillAmt = ramp(p, 0.72, 0.86);
      radialAmt = Math.max(grow * (1 - ramp(p, 0.55, 0.75)), shockAmt);
      glCanvas.style.opacity = "1";
    },
    still(p) {
      clearStroke();
      setBlade(0, 0, 0);
      const slots = [0, 0.3, 0.56];
      stillLines.forEach((line, i) => {
        const inn = i === 0 ? 1 : easeOut(ramp(p, slots[i], slots[i] + 0.1));
        const out = i < stillLines.length - 1 ? ramp(p, slots[i + 1] - 0.02, slots[i + 1] + 0.08) : 0;
        line.style.opacity = String(inn * (1 - out));
        line.style.transform = `translate3d(0, ${(1 - inn) * 16}px, 0)`;
      });
      stillNote.style.opacity = String(easeOut(ramp(p, 0.7, 0.86)));
      target = { x: Math.max(72, window.innerWidth * 0.12), y: window.innerHeight * 0.62 };
      shockAmt = 0;
      stillAmt = 0.85;
      radialAmt = 0;
      glCanvas.style.opacity = "0";
    },
    credits(p) {
      clearStroke();
      setBlade(0, 0, 0);
      colo.style.opacity = String(1 - ramp(p, 0.32, 0.52));
      const irisP = easeInOut(ramp(p, 0.38, 0.8));
      iris.style.transform = `translate(-50%, -50%) scale(${irisP})`;
      again.style.opacity = String(ramp(p, 0.74, 0.88));
      endCue.style.opacity = String(ramp(p, 0.8, 0.92));
      const from = { x: window.innerWidth * 0.2, y: window.innerHeight * 0.42 };
      target = mix(from, flightPx(0), easeInOut(ramp(p, 0.34, 0.78)));
      shockAmt = 0;
      stillAmt = 0;
      radialAmt = 0;
      glCanvas.style.opacity = String(ramp(p, 0.45, 0.7));
    },
  };

  const draw = (now: number) => {
    const live = acts.filter((act) => act.active);
    const act = live[live.length - 1] ?? acts[0];
    const prev = act.prev;
    render[act.id](act.p);
    if (act.p > prev && act.p - prev < 0.18) {
      for (const beat of BEATS) {
        if (beat.act !== act.id) continue;
        if (prev < beat.at && act.p >= beat.at) {
          const x = springX.x;
          const y = springY.x;
          fx.hit(x, y, beat.glyph, beat.rot, beat.mode);
          sfx.play(beat.sfx);
          if (beat.mode === "hit" || beat.mode === "slash") {
            document.documentElement.classList.add("is-hit");
            window.setTimeout(() => document.documentElement.classList.remove("is-hit"), 380);
            shakeStep = 0;
            shakeClock = now;
          }
        }
      }
    }
    act.prev = act.p;

    const x = springX.step(target.x);
    const y = springY.step(target.y);
    const speed = Math.hypot(springX.v, springY.v);
    const angle = Math.atan2(springY.v, springX.v);
    spark.classList.toggle("is-smear", speed > 10);
    spark.style.transform = `translate(${x}px, ${y}px) rotate(${speed > 10 ? angle : 0}rad)`;

    const kakoiInside = act.id === "kakoi" && act.p > 0.46;
    const paperChrome =
      act.id === "neko" || act.id === "still" || kakoiInside || (act.id === "credits" && act.p < 0.62);
    const paperSpark = paperChrome || act.id === "kakoi";
    spark.classList.toggle("on-paper", paperSpark);
    document.documentElement.classList.toggle("on-paper", paperChrome);
    brandMark.src = paperChrome ? "/brand/neko-peek-mark.svg" : "/brand/neko-peek-mark-on-dark.svg";
    theme.content = paperChrome ? "#F3EEE4" : "#07080C";

    shock.style.opacity = String(shockAmt);
    shock.style.transform = `translate(${x}px, ${y}px) scale(${0.12 + shockScale})`;

    if (shakeStep >= 0) {
      if (now - shakeClock > 40) {
        shakeClock = now;
        shakeStep += 1;
      }
      const mag = shakeFrames[Math.min(shakeStep, shakeFrames.length - 1)] ?? 0;
      document.querySelectorAll<HTMLElement>(".act__shake").forEach((el) => {
        el.style.translate = `${mag}px ${mag * -0.45}px`;
      });
      if (shakeStep >= shakeFrames.length) shakeStep = -1;
    }

    fx.fade();
    const scrollMax = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const globalP = lenis.animatedScroll / scrollMax;
    const vel = Math.min(1, Math.abs(lenis.velocity) / 1400);
    const flying = act.id === "spark" && act.p > 0.08 && act.p < 0.52;
    if ((vel > 0.12 && act.id !== "still") || flying) fx.streaks(flying ? 0.62 : vel);
    if (shockAmt > 0.25) fx.radial(x, y, 0.35 + shockAmt);
    if (radialAmt > 0.02) fx.radial(x, y, radialAmt);

    if (glOn) {
      ink.draw({
        time: (now - started) / 1000,
        scroll: globalP,
        vel,
        impact: shockAmt * 0.4 + (document.documentElement.classList.contains("is-hit") ? 0.8 : 0),
        sparkX: x / window.innerWidth,
        sparkY: y / window.innerHeight,
        still: stillAmt,
      });
    }

    actLabel.textContent = act.label;
    const climbing = !(act.id === "still" || (act.id === "work" && act.p > 0.64 && act.p < 0.9));
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
  if (mobile()) {
    return along(
      [
        { x: w * 0.78, y: h * 0.32 },
        { x: w * 0.5, y: h * 0.4 },
        { x: w * 0.62, y: h * 0.48 },
        { x: w * 0.4, y: h * 0.56 },
        { x: w * 0.8, y: h * 0.66 },
      ],
      p,
    );
  }
  const panels = [...document.querySelectorAll<HTMLElement>(".panel")];
  if (panels.length < 4) return { x: w * 0.5, y: h * 0.5 };
  const r = panels.map((panel) => panel.getBoundingClientRect());
  return along(
    [
      { x: r[0].left + 12, y: r[0].top + 8 },
      { x: r[0].right - 10, y: r[0].top + 8 },
      { x: r[1].right - 16, y: r[1].top + r[1].height * 0.5 },
      { x: r[2].left + 20, y: r[2].top + 10 },
      { x: r[3].left + r[3].width * 0.45, y: r[3].bottom - 16 },
      { x: w * 0.9, y: h * 0.58 },
    ],
    p,
  );
}

declare global {
  interface Window {
    __WIII?: {
      lenis: Lenis;
      scrollToAct: (id: string, progress: number) => void;
    };
  }
}
