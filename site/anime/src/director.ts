import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { Sfx } from "./audio";
import { mountBattle, type ActName } from "./battle";
import { StageFX } from "./fx";
import { upgradeArt } from "./art";
import { enableTilt, mountWeather, setWeatherCues, viewSize, weatherAudio, weatherFrame, weatherGust, weatherImpact, weatherResize } from "./weather";

gsap.registerPlugin(ScrollTrigger);

type Beat = { act: ActName; at: number; glyph: string; rot: number; mode: "major" | "micro" | "quiet"; sfx: "impact" | "slash" | "sub" | "tick" | "quiet" | "whoosh" };

const BEATS: Beat[] = [
  { act: "intrusion", at: 0.28, glyph: "ワァッ", rot: -8, mode: "micro", sfx: "whoosh" },
  { act: "clash", at: 0.32, glyph: "ズバッ", rot: -8, mode: "major", sfx: "impact" },
  { act: "observe", at: 0.16, glyph: "ピタッ", rot: 4, mode: "quiet", sfx: "tick" },
  { act: "neko", at: 0.42, glyph: "トンッ", rot: 11, mode: "micro", sfx: "slash" },
  { act: "kakoi", at: 0.2, glyph: "囲", rot: -4, mode: "major", sfx: "sub" },
  { act: "kakoi", at: 0.9, glyph: "", rot: 0, mode: "major", sfx: "quiet" },
  { act: "still", at: 0.14, glyph: "シーン", rot: 0, mode: "quiet", sfx: "quiet" },
];

const RULES = [0.26, 0.36, 0.42, 0.7, 0.86];

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export async function start(): Promise<void> {
  const restoredY = window.scrollY;
  void upgradeArt();
  // Touch devices get Lenis virtual scroll so a fling eases instead of stepping.
  // This Lenis exposes touchInertiaExponent (default 1.7), not touchInertiaMultiplier.
  // An exponent in the 25–35 range would explode the fling, so inertia stays at 1.7
  // and syncTouchLerp 0.075 does the damping. Wheel lerp stays 0.085.
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches || navigator.maxTouchPoints > 0;
  const lenis = new Lenis({
    autoRaf: false,
    lerp: 0.085,
    smoothWheel: true,
    syncTouch: coarsePointer,
    syncTouchLerp: 0.075,
    anchors: true,
    respectReducedMotion: false,
  });
  ScrollTrigger.config({ ignoreMobileResize: true });
  lenis.on("scroll", ScrollTrigger.update);

  const impact = document.getElementById("impact-plate") as HTMLElement;
  const panels = [...document.querySelectorAll<HTMLElement>("#clash-panels .panel")];
  const rules = [...document.querySelectorAll<HTMLElement>("#domain .rule")];
  const nekoLine = document.getElementById("neko-line") as HTMLElement;
  const nekoNext = document.getElementById("neko-next") as HTMLElement;
  const actLabel = document.getElementById("act-label") as HTMLElement;
  const frameLabel = document.getElementById("frame-label") as HTMLElement;
  const theme = document.getElementById("theme-color") as HTMLMetaElement;
  const shade = document.getElementById("shade") as HTMLElement;
  const reel = [...document.querySelectorAll<HTMLAnchorElement>(".stamps a")];
  const fx = new StageFX(
    document.getElementById("fxc") as HTMLCanvasElement,
    document.getElementById("flash") as HTMLElement,
    shade,
    document.getElementById("glyph") as HTMLElement,
    document.getElementById("grain") as HTMLElement,
  );
  const sfx = new Sfx();
  const sound = document.getElementById("sound") as HTMLButtonElement;
  sound.addEventListener("click", async () => {
    const on = await sfx.toggle();
    sound.setAttribute("aria-pressed", on ? "true" : "false");
    sound.lastChild!.textContent = on ? " Sound on" : " Sound off";
    if (on) enableTilt();
  });
  const snow = document.getElementById("snow") as HTMLCanvasElement;
  mountWeather(snow);
  setWeatherCues({
    crystal: () => sfx.crystal(),
    crackle: () => sfx.crackle(),
  });
  const hero = document.getElementById("hero-flake") as HTMLElement;
  const brand = document.querySelector(".brand") as HTMLElement;
  let shownFrame = -1;
  let eyeSparked = false;
  let eyeClosed = false;
  let flakeLanded = false;
  let cold = restoredY <= 24;
  let coldEyeUntil = 0;
  const coldFrom = performance.now();
  const coldAnchor = restoredY;
  const flashTimes: number[] = [];
  let cutTimers: number[] = [];
  let lastFlash = -1e9;
  let endLatch: number | null = null;
  let seenHeight = 0;
  let viewP = 0;
  let viewV = 0;
  let rawP = 0;
  let springAct: ActName = "awaken";
  let springAt = performance.now();
  let forceSnap = false;
  document.documentElement.style.minHeight = "";
  if (cold) document.documentElement.classList.add("is-cold");
  else {
    document.documentElement.classList.remove("is-cold");
    if (restoredY > 24) lenis.scrollTo(restoredY, { immediate: true, force: true });
  }
  const battle = mountBattle(sfx, (text, x, y) => {
    fx.strike(x, y, text, -4, "micro");
  });

  const acts = (
    [
      ["awaken", "00 Awaken"],
      ["intrusion", "01 Intrusion"],
      ["clash", "02 Clash"],
      ["observe", "03 Observe"],
      ["neko", "04 Neko"],
      ["kakoi", "05 Kakoi"],
      ["still", "06 Still"],
      ["return", "07 Return"],
    ] as const
  ).map(([id, label]) => {
    const el = document.getElementById(`act-${id}`) as HTMLElement;
    const pin = el.querySelector(".act__pin") as HTMLElement;
    return { id, el, pin, label, p: 0, prev: 0 };
  });
  acts[0].el.classList.add("is-cover");

  for (const act of acts) {
    ScrollTrigger.create({
      trigger: act.el,
      start: "top top",
      end: "bottom bottom",
      pin: act.pin,
      pinSpacing: false,
      anticipatePin: 1,
      onUpdate: (self) => {
        act.p = self.progress;
      },
    });
  }

  let shown = acts[0];
  let lastAct: ActName = "awaken";
  let slammed = -1;
  let nekoBurst = false;
  const colophon = document.getElementById("colophon") as HTMLElement;
  const queued: { beat: Beat; at: number }[] = [];
  let shook = false;

  const narrow = () => document.documentElement.clientWidth <= 800;
  const cam = (id: string, scale: number, x: number, y: number, rot = 0) => {
    const img = document.querySelector<HTMLElement>(`#act-${id} .splash.burst img, #act-${id} .splash:not(.residue) img`);
    if (!img) return;
    const s = narrow() ? Math.min(scale, 1.05) : scale;
    const k = narrow() ? 0.2 : 1;
    img.style.transform = `scale(${s}) translate(${x * k}%, ${y * k}%) rotate(${rot * k}deg)`;
  };
  const quant = (v: number, steps: number) => Math.round(clamp01(v) * steps) / steps;

  const render: Record<ActName, (p: number) => void> = {
    awaken(p) {
      cam("awaken", lerp(1.35, 1.18, p), lerp(8, 2, p), lerp(-6, 0, p));
    },
    intrusion(p) {
      cam("intrusion", lerp(1.28, 1.16, p), lerp(-6, 2, p), lerp(2, -2, p));
    },
    clash(p) {
      const el = document.getElementById("act-clash") as HTMLElement;
      const invert = p >= 0.12 && p < 0.2;
      const shatter = p >= 0.2 && p < 0.28;
      const hold = p >= 0.28;
      el.classList.toggle("is-invert", invert);
      el.classList.toggle("is-shatter", shatter || hold);
      el.classList.toggle("is-hold", hold);
      impact.style.opacity = invert ? "1" : "0";
      cam("clash", hold || shatter ? 1.05 : lerp(1.32, 1.14, p), hold ? 0 : lerp(6, -2, p), 0);
      panels.forEach((panel) => panel.classList.toggle("is-in", hold));
    },
    observe(p) {
      const shot = document.querySelector<HTMLElement>("#act-observe .splash img");
      if (narrow() && shot) {
        const q = quant(p, 8);
        shot.style.transformOrigin = "62% 38%";
        shot.style.transform = `scale(${lerp(1.12, 1.92, q)}) translate(${lerp(10, -8, q)}%, ${lerp(-3, 6, q)}%) rotate(${lerp(1.4, -4.2, q)}deg)`;
        const depth = q > 0.72 ? (q - 0.72) / 0.28 : 0;
        shot.style.filter = depth > 0.05 ? `contrast(${(1.04 + depth * 0.14).toFixed(3)})` : "";
      } else {
        cam("observe", lerp(1.22, 1.12, p), lerp(4, 0, p), 0);
        shot?.style.removeProperty("filter");
        shot?.style.removeProperty("transform-origin");
      }
      document.getElementById("act-observe")?.classList.toggle("is-hold", p > 0.12);
    },
    neko(p) {
      const el = document.getElementById("act-neko") as HTMLElement;
      const burst = p >= 0.42;
      el.classList.toggle("is-residue", !burst);
      nekoLine.hidden = burst;
      nekoNext.hidden = !burst;
      if (burst !== nekoBurst) {
        nekoBurst = burst;
        const plate = burst ? nekoNext : nekoLine;
        plate.classList.remove("is-struck");
        void plate.offsetWidth;
        plate.classList.add("is-struck");
        window.setTimeout(() => plate.classList.remove("is-struck"), 200);
      }
      if (narrow()) {
        const wait = el.querySelector<HTMLElement>(".splash.residue img");
        const jump = el.querySelector<HTMLElement>(".splash.burst img");
        if (wait) {
          const q = quant(clamp01(p / 0.42), 6);
          wait.style.transformOrigin = "74% 40%";
          wait.style.transform = `scale(${lerp(1.46, 2.28, q)}) translate(${lerp(16, -24, q)}%, ${lerp(1, 9, q)}%) rotate(${lerp(2.6, -6.2, q)}deg)`;
          const depth = q > 0.66 ? (q - 0.66) / 0.34 : 0;
          wait.style.filter = depth > 0.05 ? `contrast(${(1.04 + depth * 0.16).toFixed(3)})` : "";
        }
        if (jump) {
          const q = burst ? quant((p - 0.42) / 0.58, 7) : 0;
          jump.style.transform = `scale(${lerp(1.72, 2.12, q)}) translate(${lerp(2, -3, q)}%, ${lerp(4, 0, q)}%) rotate(${lerp(-1.4, 2.4, q)}deg)`;
          jump.style.filter = "";
        }
        return;
      }
      if (burst) {
        const q = quant((p - 0.42) / 0.58, 7);
        cam("neko", lerp(1.04, 1.18, q), lerp(3, -2, q), lerp(1, -3, q), lerp(-2, 2.4, q));
      }
    },
    kakoi(p) {
      const el = document.getElementById("act-kakoi") as HTMLElement;
      const black = document.getElementById("kakoi-black") as HTMLElement;
      const open = p >= 0.3;
      const domain = p >= 0.26;
      el.classList.toggle("is-residue", false);
      el.classList.toggle("is-domain", domain);
      el.classList.toggle("is-mark", p < 0.26);
      black.style.opacity = p < 0.18 ? "1" : p < 0.26 ? String(1 - (p - 0.18) / 0.08) : "0";
      const mark = el.querySelector<HTMLElement>(".ono--kakoi");
      if (mark) {
        if (narrow() && p < 0.26) {
          const q = quant(p / 0.26, 5);
          mark.style.fontSize = `${lerp(86, 118, q).toFixed(1)}vw`;
          mark.style.transform = `translate(-50%, -50%) rotate(${lerp(-13, -2.5, q).toFixed(2)}deg)`;
        } else {
          mark.style.removeProperty("font-size");
          mark.style.removeProperty("transform");
        }
      }
      const shot = el.querySelector<HTMLElement>(".splash.burst img");
      if (domain && shot) {
        if (narrow()) {
          let scale = 1.08;
          let x = 0;
          let y = 0;
          let rot = 0;
          let origin = "50% 58%";
          if (p < 0.42) {
            const q = quant((p - 0.26) / 0.16, 3);
            scale = lerp(1.02, 1.16, q);
            rot = lerp(0.4, -0.6, q);
          } else if (p < 0.7) {
            const q = quant((p - 0.42) / 0.28, 4);
            scale = lerp(1.2, 1.46, q);
            x = lerp(2, -4, q);
            y = lerp(2, 6, q);
            rot = lerp(-0.8, 1.8, q);
            origin = "46% 64%";
          } else {
            const q = quant((p - 0.7) / 0.3, 4);
            scale = lerp(1.62, 2.08, q);
            x = lerp(1, -2, q);
            y = lerp(-6, -12, q);
            rot = lerp(-1.4, -3.6, q);
            origin = "52% 34%";
          }
          shot.style.transformOrigin = origin;
          shot.style.transform = `scale(${scale}) translate(${x}%, ${y}%) rotate(${rot}deg)`;
        } else {
          const late = p >= 0.7;
          const q = late ? quant((p - 0.7) / 0.3, 4) : quant((p - 0.26) / 0.44, 4);
          shot.style.transformOrigin = late ? "50% 38%" : "50% 58%";
          shot.style.transform = late
            ? `scale(${lerp(1.18, 1.34, q)}) translate(${lerp(0, -2, q)}%, ${lerp(-3, -7, q)}%) rotate(${lerp(-0.6, -1.8, q)}deg)`
            : `scale(${lerp(1.04, 1.1, q)}) translate(${lerp(1, -1, q)}%, 0%)`;
        }
      } else if (shot) {
        shot.style.removeProperty("transform");
        shot.style.removeProperty("transform-origin");
      }
      let idx = -1;
      for (let i = 0; i < RULES.length; i++) if (p >= RULES[i]) idx = i;
      rules.forEach((rule, i) => {
        const now = open && i === idx;
        rule.classList.toggle("is-now", now);
        rule.classList.toggle("is-debris", open && i < idx);
        if (now && i !== slammed) {
          slammed = i;
          const box = rule.getBoundingClientRect();
          fx.strike(box.left + box.width * 0.5, box.top + Math.min(box.height * 0.45, 36), "", 0, "micro");
          sfx.play("tick");
          document.documentElement.classList.add("is-slam");
          window.setTimeout(() => document.documentElement.classList.remove("is-slam"), 180);
        }
      });
    },
    still(p) {
      cam("still", lerp(1.02, 1.04, p), -6, 0);
    },
    return(p) {
      const shot = document.querySelector<HTMLElement>("#act-return .splash img");
      const el = document.getElementById("act-return");
      if (narrow() && shot) {
        const q = quant(clamp01(p / 0.7), 6);
        shot.style.transformOrigin = "38% 30%";
        shot.style.transform = `scale(${lerp(1.52, 2.18, q)}) translate(${lerp(6, -1, q)}%, ${lerp(3, -8, q)}%)`;
        shot.style.filter = p >= 0.6 ? "contrast(1.18) brightness(0.62)" : "";
      } else {
        cam("return", lerp(1.42, 1.62, p), lerp(4, -2, p), lerp(6, 2, p));
        shot?.style.removeProperty("filter");
        shot?.style.removeProperty("transform-origin");
      }
      el?.classList.toggle("is-after", p >= 0.78);
    },
  };

  const motif = document.getElementById("motif") as HTMLElement;
  const stage = ["grain", "snow", "wash", "wiii-cut", "drift-cut", "ghosts", "drift-arms", "drift-face", "hero-flake", "motif", "spark", "fxc"]
    .map((id) => document.getElementById(id))
    .filter((node): node is HTMLElement => Boolean(node));
  // A fixed pin is a stacking context. These layers have to live inside it,
  // under the plates, or the canvases paint over the type.
  const seatLayers = (pin: HTMLElement) => {
    for (const node of stage) if (node.parentElement !== pin) pin.append(node);
  };
  const handoff = (id: ActName, p: number) => {
    let kind = "";
    if ((id === "awaken" && p > 0.72) || (id === "intrusion" && p < 0.5)) kind = "spark";
    else if ((id === "intrusion" && p > 0.72) || (id === "clash" && p < 0.48)) kind = "cursor";
    else if ((id === "clash" && p > 0.72) || (id === "observe" && p < 0.55)) kind = "ink";
    else if ((id === "observe" && p > 0.72) || (id === "neko" && p < 0.42)) kind = "cursor";
    else if ((id === "neko" && p > 0.72) || (id === "kakoi" && p < 0.06)) kind = "ring";
    else if (id === "still" || id === "return") kind = "";
    motif.dataset.kind = kind;
    motif.dataset.act = id;
    motif.classList.toggle("is-on", kind !== "");
    motif.toggleAttribute("data-drift", kind === "cursor");
  };
  const loopFrom = (x: number, y: number, cx: number, cy: number) => {
    const a0 = Math.atan2(y - cy, x - cx);
    const r = Math.max(80, Math.hypot(x - cx, y - cy));
    const n = 8;
    let d = `M ${x.toFixed(1)} ${y.toFixed(1)}`;
    for (let i = 1; i <= n; i++) {
      const a = a0 + (i / n) * Math.PI * 2;
      const wobble = 1 + 0.065 * Math.sin(a * 3 + 0.4);
      const endX = i === n ? x : cx + Math.cos(a) * r * wobble;
      const endY = i === n ? y : cy + Math.sin(a) * r * wobble;
      const c1a = a0 + ((i - 0.7) / n) * Math.PI * 2;
      const c2a = a0 + ((i - 0.3) / n) * Math.PI * 2;
      d += ` C ${(cx + Math.cos(c1a) * r).toFixed(1)} ${(cy + Math.sin(c1a) * r).toFixed(1)}, ${(cx + Math.cos(c2a) * r).toFixed(1)} ${(cy + Math.sin(c2a) * r).toFixed(1)}, ${endX.toFixed(1)} ${endY.toFixed(1)}`;
    }
    return d;
  };
  const seatRing = (p: number) => {
    const ring = document.querySelector("#ring-stroke") as SVGPathElement;
    const inner = document.querySelector("#ring-inner") as SVGPathElement;
    const svg = document.getElementById("kakoi-ring") as HTMLElement;
    const figure = document.getElementById("wiii-cut") as HTMLElement;
    const box = svg.getBoundingClientRect();
    const wr = figure.getBoundingClientRect();
    if (box.width < 8 || wr.width < 8) return;
    // Scarf cloth, just in from the flying tip (image fractions of the cutout).
    const tipX = wr.left + wr.width * 0.95;
    const tipY = wr.top + wr.height * 0.215;
    const bodyX = wr.left + wr.width * 0.4;
    const bodyY = wr.top + wr.height * 0.5;
    const vx = ((tipX - box.left) / box.width) * 1000;
    const vy = ((tipY - box.top) / box.height) * 1000;
    const cx = ((bodyX - box.left) / box.width) * 1000;
    const cy = ((bodyY - box.top) / box.height) * 1000;
    const d = loopFrom(vx, vy, cx, cy);
    ring.setAttribute("d", d);
    inner.setAttribute("d", d);
    const drawn = clamp01(p / 0.16);
    for (const node of [ring, inner]) {
      const len = node.getTotalLength();
      node.style.strokeDasharray = `${len}`;
      node.style.strokeDashoffset = `${len * (1 - drawn)}`;
    }
  };

  const liftSnow = () => {
    if (snow.parentElement !== document.body) document.body.append(snow);
    if (hero.parentElement !== document.body) document.body.append(hero);
  };
  const strikeType = (pin: HTMLElement) => {
    const plate = [...pin.querySelectorAll<HTMLElement>(".plate")].find((el) => !el.hidden);
    if (!plate) return;
    plate.classList.remove("is-struck");
    void plate.offsetWidth;
    plate.classList.add("is-struck");
    window.setTimeout(() => plate.classList.remove("is-struck"), 200);
  };
  const liveMax = () => {
    const el = document.documentElement;
    const view = window.visualViewport?.height || el.clientHeight;
    return el.scrollHeight - view;
  };
  const releaseScrollLock = () => {
    lenis.start();
    for (const node of [document.documentElement, document.body]) {
      if (node.style.overflow === "hidden" || node.style.overflow === "clip") node.style.overflow = "";
      if (node.style.overflowY === "hidden" || node.style.overflowY === "clip") node.style.overflowY = "";
    }
  };
  const endCold = (reveal: boolean) => {
    releaseScrollLock();
    if (!cold) return;
    cold = false;
    document.documentElement.classList.remove("is-cold");
    if (!reveal) return;
    coldEyeUntil = performance.now() + 900;
    sfx.crystal();
    strikeType(acts[0].pin);
  };
  const playCut = () => {
    const root = document.documentElement;
    for (const timer of cutTimers) window.clearTimeout(timer);
    cutTimers = [];
    root.classList.remove("is-cut-black", "is-cut-ink", "is-cut-wipe", "is-hitstop");
    root.classList.add("is-cut-black", "is-hitstop");
    if (sfx.enabled) sfx.duckWind(0.09);
    const later = (ms: number, fn: () => void) => {
      cutTimers.push(window.setTimeout(fn, ms));
    };
    later(40, () => {
      root.classList.remove("is-cut-black", "is-hitstop");
      const flash = flashTimes.every((t) => performance.now() - t > 420);
      if (flash) {
        lastFlash = performance.now();
        flashTimes.push(lastFlash);
        root.classList.add("is-cut-ink");
      } else root.classList.add("is-cut-wipe");
    });
    later(80, () => {
      root.classList.remove("is-cut-ink", "is-cut-black");
      root.classList.add("is-cut-wipe");
    });
    later(150, () => root.classList.remove("is-cut-black", "is-cut-ink", "is-cut-wipe", "is-hitstop"));
  };
  const stabilizeEnd = () => {
    const el = document.documentElement;
    if (el.style.minHeight) el.style.minHeight = "";
    const y = Math.round(window.scrollY);
    const max = liveMax();
    if (max <= 1) {
      endLatch = null;
      return;
    }
    if (endLatch !== null && (max - endLatch > 6 || y < endLatch - 12)) {
      endLatch = null;
      return;
    }
    if (endLatch === null) {
      if (max - y <= 6) endLatch = y;
      return;
    }
    if (y > endLatch && max - y <= 6) endLatch = y;
    const current = Math.round(window.scrollY);
    if (max - endLatch <= 6 && Math.abs(current - endLatch) > 0 && Math.abs(current - endLatch) <= 6) {
      lenis.scrollTo(endLatch, { immediate: true, force: true });
    }
  };
  let refreshTimer = 0;
  const refreshLayout = () => {
    const y = window.scrollY;
    ScrollTrigger.refresh();
    lenis.resize();
    const max = Math.max(0, liveMax());
    const next = Math.min(Math.max(0, y), max);
    if (Math.abs(window.scrollY - next) > 1) lenis.scrollTo(next, { immediate: true, force: true });
    seenHeight = document.documentElement.scrollHeight;
    if (endLatch !== null && max - endLatch > 6) endLatch = null;
  };
  const scheduleRefresh = () => {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(refreshLayout, 80);
  };
  const watchImages = () => {
    for (const img of document.images) {
      if (img.complete) continue;
      img.addEventListener("load", scheduleRefresh, { once: true });
    }
  };
  const trackHeight = () => {
    const h = document.documentElement.scrollHeight;
    if (h === seenHeight) return;
    const grew = seenHeight > 0 && h > seenHeight + 6;
    seenHeight = h;
    lenis.resize();
    if (grew) endLatch = null;
  };

  const draw = (now: number) => {
    if (cold && Math.abs(window.scrollY - coldAnchor) > 24) endCold(false);
    const viewingColo = window.scrollY + 24 >= colophon.offsetTop;
    document.documentElement.classList.toggle("is-colophon", viewingColo);
    if (viewingColo) {
      viewP = 1;
      viewV = 0;
      rawP = 1;
      springAct = "return";
      springAt = now;
      forceSnap = false;
      for (const item of acts) item.el.classList.remove("is-cover");
      document.documentElement.classList.add("on-paper");
      theme.content = "#F3EEE3";
      actLabel.textContent = "07 Return";
      battle.setAct("return", 1);
      document.documentElement.dataset.act = "return";
      const snow = document.getElementById("snow");
      if (snow && snow.parentElement !== document.body) document.body.append(snow);
      const box = viewSize();
      weatherFrame(now, { act: "still", p: 1, pointerX: box.w * 0.5, pointerY: box.h * 0.18, scroll: 0, scarf: null });
      sfx.wind(0, false);
      sfx.bed(sfx.enabled ? "still" : null);
      hero.style.opacity = "0";
      battle.draw(now, 0);
      if (!fx.holding) fx.fade();
      return;
    }
    // anticipatePin can mark the next section active during a fast fling.
    // The story follows the section whose top has actually reached the viewport.
    const y = window.scrollY + 2;
    shown = acts[0];
    for (const item of acts) if (item.el.offsetTop <= y) shown = item;
    const act = shown;
    for (const item of acts) item.el.classList.toggle("is-cover", item === act);
    seatLayers(act.pin);
    if (act.id !== lastAct) {
      if (!fx.holding) fx.clear();
      brand.classList.remove("is-pulse");
      void brand.offsetWidth;
      brand.classList.add("is-pulse");
      if (!cold) playCut();
      strikeType(act.pin);
      lastAct = act.id;
    }
    if (cold) liftSnow();
    const targetP = act.p;
    const dt = Math.min(0.05, Math.max(0, (now - springAt) / 1000));
    springAt = now;
    const jumped = Math.abs(targetP - rawP) >= 0.5;
    rawP = targetP;
    const snap = forceSnap || act.id !== springAct || jumped;
    forceSnap = false;
    springAct = act.id;
    if (snap || dt === 0) {
      viewP = targetP;
      viewV = 0;
    } else {
      const omega = 14;
      const sub = 3;
      const h = dt / sub;
      for (let i = 0; i < sub; i++) {
        const accel = omega * omega * (targetP - viewP) - 2 * omega * viewV;
        viewV += accel * h;
        viewP += viewV * h;
      }
      if (!Number.isFinite(viewP) || (Math.abs(targetP - viewP) < 0.0008 && Math.abs(viewV) < 0.02)) {
        viewP = targetP;
        viewV = 0;
      }
    }
    const smooth = clamp01(viewP);
    render[act.id](smooth);
    battle.setAct(act.id, smooth);
    if (act.id === "kakoi") seatRing(smooth);
    handoff(act.id, smooth);
    document.documentElement.dataset.act = act.id;
    document.documentElement.dataset.p = act.p.toFixed(3);
    sfx.bed(sfx.enabled ? act.id : null);

    if (act.p > act.prev && act.p - act.prev < 0.2) {
      for (const beat of BEATS) {
        if (beat.act !== act.id) continue;
        if (act.prev < beat.at && act.p >= beat.at) {
          if (beat.mode === "major") queued.push({ beat, at: now + 140 });
          else {
            const box = viewSize();
            fx.strike(box.w * 0.5, box.h * 0.46, beat.glyph, beat.rot, beat.mode);
            sfx.play(beat.sfx);
          }
        }
      }
    }
    for (let i = queued.length - 1; i >= 0; i--) {
      if (now < queued[i].at) continue;
      const beat = queued[i].beat;
      const box = viewSize();
      weatherImpact();
      sfx.silence(0.25);
      fx.strike(box.w * 0.5, box.h * 0.46, beat.glyph, beat.rot, "major");
      window.setTimeout(() => sfx.play(beat.sfx), 260);
      const root = document.documentElement;
      root.classList.add("is-strike-smear");
      window.setTimeout(() => {
        root.classList.remove("is-strike-smear");
        battle.recoil();
        root.classList.add("is-hit");
        if (!shook) {
          shook = true;
          window.setTimeout(() => {
            root.classList.remove("is-hit");
            shook = false;
          }, 420);
        }
      }, 83);
      queued.splice(i, 1);
    }
    act.prev = act.p;

    const vel = Math.min(1, Math.abs(lenis.velocity) / 1400);
    const root = document.documentElement;
    root.classList.toggle("is-smear", vel > 0.22);
    root.classList.toggle(
      "is-cam",
      vel > 0.04 || root.classList.contains("is-smear") || root.classList.contains("is-hitstop") || root.classList.contains("is-cut-wipe") || root.classList.contains("is-strike-smear"),
    );
    const box = viewSize();
    const sparkEl = document.getElementById("spark") as HTMLElement;
    const placed = /translate\(([-\d.]+)px,\s*([-\d.]+)px\)/.exec(sparkEl.style.transform);
    const wiii = document.getElementById("wiii-cut") as HTMLElement;
    const wr = wiii.getBoundingClientRect();
    const scarf = Number(wiii.style.opacity) > 0.2
      ? { x: wr.left + wr.width * 0.92, y: wr.top + wr.height * 0.22 }
      : act.id === "intrusion"
        ? { x: box.w * 0.22, y: box.h * 0.62 }
        : null;
    const flakeT = act.id === "awaken" && smooth < 0.4
      ? smooth / 0.4
      : act.id === "return" && smooth > 0.08 && smooth < 0.62
        ? (smooth - 0.08) / 0.54
        : -1;
    if (cold) {
      const elapsed = now - coldFrom;
      if (elapsed < 1700) hero.style.opacity = "0";
      else {
        const t = clamp01((elapsed - 1700) / 420);
        const y = -24 + t * (box.h * 0.36 + 24);
        hero.style.opacity = "1";
        hero.style.transform = `translate(${box.w * (narrow() ? 0.5 : 0.42)}px, ${y}px)`;
        hero.style.setProperty("--path", `${Math.max(16, y)}px`);
        if (t >= 1) endCold(true);
      }
    } else if (flakeT >= 0) {
      const returning = act.id === "return";
      const x = box.w * (returning ? (narrow() ? 0.38 : 0.42) : narrow() ? 0.5 : 0.42);
      const landY = returning ? box.h * (narrow() ? 0.3 : 0.34) : box.h * 0.34;
      const startY = returning ? box.h * 0.04 : -28;
      const fade = returning ? Math.max(0, (flakeT - 0.86) / 0.14) : 0;
      const y = startY + flakeT * (landY - startY);
      hero.style.opacity = String(1 - fade);
      hero.style.transform = `translate(${x}px, ${y}px)`;
      if (returning) hero.style.setProperty("--path", `${Math.max(16, y)}px`);
      else hero.style.removeProperty("--path");
    } else {
      hero.style.opacity = "0";
      hero.style.removeProperty("--path");
    }
    if (coldEyeUntil && now > coldEyeUntil) coldEyeUntil = 0;
    const scrollEye = act.id === "awaken" && smooth >= 0.36 && smooth < 0.72;
    document.documentElement.classList.toggle("is-eye-open", scrollEye || now < coldEyeUntil);
    const shut = act.id === "return" && smooth >= 0.6;
    document.documentElement.classList.toggle("is-eye-shut", shut);
    if (act.id !== "return" || smooth < 0.48) {
      eyeClosed = false;
      flakeLanded = false;
      document.documentElement.classList.remove("is-flake");
    }
    if (act.id === "return" && smooth >= 0.54 && !flakeLanded) {
      flakeLanded = true;
      document.documentElement.classList.add("is-flake");
      sfx.crystal();
      const land = viewSize();
      weatherGust(land.w * (narrow() ? 0.38 : 0.42), land.h * (narrow() ? 0.3 : 0.34), 0, 240);
    }
    if (shut && !eyeClosed) {
      eyeClosed = true;
      sfx.silence(0.32);
    }
    if (act.id === "awaken" && smooth >= 0.36 && !eyeSparked) {
      eyeSparked = true;
      sfx.play("spark");
    }
    weatherFrame(now, {
      act: act.id,
      p: smooth,
      pointerX: placed ? Number(placed[1]) : box.w * 0.5,
      pointerY: placed ? Number(placed[2]) : box.h * 0.42,
      scroll: vel,
      scarf,
    });
    const audio = weatherAudio();
    if (cold && sfx.enabled) sfx.wind(0.42, false);
    else sfx.wind(audio.strength, audio.ember);
    battle.draw(now, vel);
    if (!fx.holding) {
      shade.style.opacity = "0";
      fx.fade();
    }

    const paper = act.id === "still" || (act.id === "kakoi" && smooth >= 0.24);
    document.documentElement.classList.toggle("on-paper", paper);
    theme.content = paper ? "#F3EEE3" : "#0B0B0D";
    actLabel.textContent = act.label;
    const twos = Math.floor(now / 83);
    if (twos !== shownFrame) {
      shownFrame = twos;
      const max = Math.max(1, document.documentElement.scrollHeight - viewSize().h);
      const target = Math.round((lenis.animatedScroll / max) * 2400 + 1);
      frameLabel.textContent = `F ${String(target).padStart(4, "0")}`;
      document.documentElement.classList.toggle("is-twos", twos % 2 === 1);
      for (const link of reel) {
        link.setAttribute("aria-current", link.getAttribute("href") === `#act-${act.id}` ? "true" : "false");
      }
    }
  };

  window.__WIII = {
    strikes: 0,
    flashTimes,
    lenis,
    scrollToAct(id: string, progress: number) {
      endCold(false);
      const el = document.getElementById(id);
      if (!el) return;
      const span = Math.max(0, el.offsetHeight - viewSize().h);
      forceSnap = true;
      lenis.scrollTo(el.offsetTop + span * clamp01(progress), { immediate: true, force: true });
      ScrollTrigger.update();
    },
  };

  gsap.ticker.lagSmoothing(0);
  gsap.ticker.add((time) => {
    lenis.raf(time * 1000);
    draw(performance.now());
    trackHeight();
    stabilizeEnd();
  });
  fx.resize();
  window.addEventListener("resize", () => {
    fx.resize();
    weatherResize();
    scheduleRefresh();
  });
  window.visualViewport?.addEventListener("resize", () => {
    fx.resize();
    weatherResize();
    lenis.resize();
  });
  watchImages();
  window.addEventListener("load", scheduleRefresh, { once: true });
  await document.fonts.ready;
  refreshLayout();
}

declare global {
  interface Window {
    __WIII?: {
      lenis?: Lenis;
      strikes: number;
      flashTimes: number[];
      scrollToAct: (id: string, progress: number) => void;
      mode?: string;
      progress?: number;
      act?: string;
      gating?: boolean;
      seal?: number;
      orient?: string;
      plate?: string;
      present?: (u: number) => string;
      debug?: () => {
        target: number;
        pos: number;
        cam: number;
        energy: number;
        locked: boolean;
        cap: number;
        total: number;
        plate: string;
        textures: string[];
        fbo: boolean;
      };
      release?: () => void;
      perf?: () => { avg: number; p95: number; n: number; dpr: number; dof: boolean };
    };
  }
}
