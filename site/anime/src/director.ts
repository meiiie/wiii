import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { Sfx } from "./audio";
import { mountBattle, type ActName } from "./battle";
import { StageFX } from "./fx";

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
  const lenis = new Lenis({ autoRaf: false, lerp: 0.085, smoothWheel: true, anchors: true, respectReducedMotion: false });
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
  });
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
    return { id, el, pin, label, p: 0, prev: 0, active: false };
  });
  acts[0].el.classList.add("is-cover");

  for (const act of acts) {
    ScrollTrigger.create({
      trigger: act.el,
      start: "top top",
      end: "bottom bottom",
      pin: act.pin,
      pinSpacing: false,
      onToggle: (self) => {
        act.active = self.isActive;
      },
      onUpdate: (self) => {
        act.p = self.progress;
      },
    });
  }

  let shown = acts[0];
  let lastAct: ActName = "awaken";
  const colophon = document.getElementById("colophon") as HTMLElement;
  const queued: { beat: Beat; at: number }[] = [];
  let shook = false;

  const cam = (id: string, scale: number, x: number, y: number, rot = 0) => {
    const img = document.querySelector<HTMLElement>(`#act-${id} .splash.burst img, #act-${id} .splash:not(.residue) img`);
    if (!img) return;
    img.style.transform = `scale(${scale}) translate(${x}%, ${y}%) rotate(${rot}deg)`;
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
      el.classList.toggle("is-shatter", shatter);
      el.classList.toggle("is-hold", hold);
      impact.style.opacity = invert || hold ? "1" : "0";
      cam("clash", hold || shatter ? 1.05 : lerp(1.32, 1.14, p), hold ? 0 : lerp(6, -2, p), 0);
      panels.forEach((panel) => panel.classList.toggle("is-in", hold));
    },
    observe(p) {
      cam("observe", lerp(1.22, 1.12, p), lerp(4, 0, p), 0);
      document.getElementById("act-observe")?.classList.toggle("is-hold", p > 0.12);
    },
    neko(p) {
      const el = document.getElementById("act-neko") as HTMLElement;
      const burst = p >= 0.42;
      el.classList.toggle("is-residue", !burst);
      nekoLine.hidden = burst;
      nekoNext.hidden = !burst;
      if (burst) {
        const q = quant((p - 0.42) / 0.58, 7);
        cam("neko", lerp(1.04, 1.18, q), lerp(3, -2, q), lerp(1, -3, q), lerp(-2, 2.4, q));
      }
    },
    kakoi(p) {
      const el = document.getElementById("act-kakoi") as HTMLElement;
      const black = document.getElementById("kakoi-black") as HTMLElement;
      const ring = document.querySelector("#ring-stroke") as SVGPathElement;
      const inner = document.querySelector("#ring-inner") as SVGPathElement;
      const drawT = clamp01(p / 0.16);
      const open = p >= 0.3;
      const domain = p >= 0.26;
      el.classList.toggle("is-residue", false);
      el.classList.toggle("is-domain", domain);
      el.classList.toggle("is-mark", p < 0.26);
      black.style.opacity = p < 0.18 ? "1" : p < 0.26 ? String(1 - (p - 0.18) / 0.08) : "0";
      const paint = (node: SVGPathElement) => {
        const len = node.getTotalLength();
        node.style.strokeDasharray = `${len}`;
        node.style.strokeDashoffset = `${len * (1 - drawT)}`;
      };
      paint(ring);
      paint(inner);
      if (domain) {
        const q = quant((p - 0.24) / 0.76, 6);
        cam("kakoi", lerp(1.04, 1.16, q), lerp(1, -1, q), lerp(1, -1, q));
      }
      let idx = -1;
      for (let i = 0; i < RULES.length; i++) if (p >= RULES[i]) idx = i;
      rules.forEach((rule, i) => {
        rule.classList.toggle("is-now", open && i === idx);
        rule.classList.toggle("is-debris", false);
      });
    },
    still() {
      cam("still", 1.02, -6, 0);
    },
    return(p) {
      cam("return", lerp(1.42, 1.62, p), lerp(4, -2, p), lerp(6, 2, p));
    },
  };

  const draw = (now: number) => {
    const viewingColo = window.scrollY + 24 >= colophon.offsetTop;
    document.documentElement.classList.toggle("is-colophon", viewingColo);
    if (viewingColo) {
      for (const item of acts) item.el.classList.remove("is-cover");
      document.documentElement.classList.add("on-paper");
      theme.content = "#F3EEE3";
      actLabel.textContent = "07 Return";
      battle.setAct("return", 1);
      document.documentElement.dataset.act = "return";
      sfx.bed(sfx.enabled ? "return" : null);
      battle.draw(now, 0);
      if (!fx.holding) fx.fade();
      return;
    }
    const live = acts.filter((item) => item.active);
    if (live.length) shown = live[live.length - 1];
    else {
      const y = window.scrollY + 8;
      for (const item of acts) if (item.el.offsetTop <= y) shown = item;
    }
    const act = shown;
    for (const item of acts) item.el.classList.toggle("is-cover", item === act);
    if (act.id !== lastAct) {
      if (!fx.holding) fx.clear();
      lastAct = act.id;
    }
    render[act.id](act.p);
    battle.setAct(act.id, act.p);
    document.documentElement.dataset.act = act.id;
    document.documentElement.dataset.p = act.p.toFixed(3);
    sfx.bed(sfx.enabled ? act.id : null);

    if (act.p > act.prev && act.p - act.prev < 0.2) {
      for (const beat of BEATS) {
        if (beat.act !== act.id) continue;
        if (act.prev < beat.at && act.p >= beat.at) {
          if (beat.mode === "major") queued.push({ beat, at: now + 140 });
          else {
            fx.strike(window.innerWidth * 0.5, window.innerHeight * 0.46, beat.glyph, beat.rot, beat.mode);
            sfx.play(beat.sfx);
          }
        }
      }
    }
    for (let i = queued.length - 1; i >= 0; i--) {
      if (now < queued[i].at) continue;
      const beat = queued[i].beat;
      fx.strike(window.innerWidth * 0.5, window.innerHeight * 0.46, beat.glyph, beat.rot, "major");
      sfx.play(beat.sfx);
      document.documentElement.classList.add("is-hit");
      if (!shook) {
        shook = true;
        window.setTimeout(() => {
          document.documentElement.classList.remove("is-hit");
          shook = false;
        }, 420);
      }
      queued.splice(i, 1);
    }
    act.prev = act.p;

    const vel = Math.min(1, Math.abs(lenis.velocity) / 1400);
    document.documentElement.classList.toggle("is-smear", vel > 0.22);
    battle.draw(now, vel);
    if (!fx.holding) {
      shade.style.opacity = "0";
      fx.fade();
    }

    const paper = act.id === "still" || (act.id === "kakoi" && act.p >= 0.24);
    document.documentElement.classList.toggle("on-paper", paper);
    theme.content = paper ? "#F3EEE3" : "#0B0B0D";
    actLabel.textContent = act.label;
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    frameLabel.textContent = `F ${String(Math.round((lenis.animatedScroll / max) * 2400 + 1)).padStart(4, "0")}`;
    for (const link of reel) {
      link.setAttribute("aria-current", link.getAttribute("href") === `#act-${act.id}` ? "true" : "false");
    }
  };

  gsap.ticker.lagSmoothing(0);
  gsap.ticker.add((time) => {
    lenis.raf(time * 1000);
    draw(performance.now());
  });
  fx.resize();
  window.addEventListener("resize", () => {
    fx.resize();
    ScrollTrigger.refresh();
  });
  await document.fonts.ready;
  ScrollTrigger.refresh();

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

declare global {
  interface Window {
    __WIII?: {
      lenis: Lenis;
      scrollToAct: (id: string, progress: number) => void;
    };
  }
}
