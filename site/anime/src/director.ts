import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { Sfx } from "./audio";
import { mountBattle, type ActName } from "./battle";
import { StageFX } from "./fx";

gsap.registerPlugin(ScrollTrigger);

type Beat = { act: ActName; at: number; glyph: string; rot: number; mode: "major" | "micro" | "quiet"; sfx: "impact" | "slash" | "sub" | "tick" | "quiet" | "whoosh" };

const BEATS: Beat[] = [
  { act: "intrusion", at: 0.22, glyph: "ワァッ", rot: -8, mode: "micro", sfx: "whoosh" },
  { act: "clash", at: 0.3, glyph: "ズバッ", rot: -6, mode: "major", sfx: "impact" },
  { act: "observe", at: 0.18, glyph: "ピタッ", rot: 4, mode: "quiet", sfx: "tick" },
  { act: "neko", at: 0.42, glyph: "トンッ", rot: 6, mode: "micro", sfx: "slash" },
  { act: "kakoi", at: 0.7, glyph: "囲", rot: 0, mode: "major", sfx: "sub" },
  { act: "still", at: 0.12, glyph: "シーン", rot: 0, mode: "quiet", sfx: "quiet" },
];

const RULES = [0.36, 0.5, 0.62, 0.74, 0.86];

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ramp = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));

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
  const queued: { beat: Beat; at: number }[] = [];
  let shook = false;

  const cam = (id: string, scale: number, x: number, y: number) => {
    const img = document.querySelector<HTMLElement>(`#act-${id} .splash img`);
    if (!img) return;
    img.style.transform = `scale(${scale}) translate(${x}%, ${y}%)`;
  };

  const render: Record<ActName, (p: number) => void> = {
    awaken(p) {
      cam("awaken", lerp(1.35, 1.18, p), lerp(8, 2, p), lerp(-6, 0, p));
    },
    intrusion(p) {
      cam("intrusion", lerp(1.28, 1.16, p), lerp(-6, 2, p), lerp(2, -2, p));
    },
    clash(p) {
      const hit = p >= 0.28 && p < 0.62;
      impact.classList.toggle("is-in", hit || p >= 0.62);
      impact.style.opacity = p >= 0.28 ? "1" : "0";
      cam("clash", hit ? 1.08 : lerp(1.32, 1.14, p), hit ? 0 : lerp(6, -4, p), 0);
      const gates = [0.48, 0.58, 0.68];
      panels.forEach((panel, i) => panel.classList.toggle("is-in", p >= gates[i]));
    },
    observe(p) {
      cam("observe", lerp(1.22, 1.12, p), lerp(4, 0, p), 0);
      document.getElementById("act-observe")?.classList.toggle("is-hold", p > 0.12);
    },
    neko(p) {
      cam("neko", lerp(1.26, 1.12, p), lerp(-4, 3, p), 0);
      const second = p >= 0.55;
      nekoLine.style.opacity = second ? "0" : "1";
      nekoNext.style.opacity = second ? "1" : "0";
    },
    kakoi(p) {
      cam("kakoi", lerp(1.2, 1.08, p), 0, lerp(2, 0, p));
      let idx = p >= 0.34 ? 0 : -1;
      if (idx === 0) for (let i = 0; i < RULES.length; i++) if (p >= RULES[i]) idx = i;
      rules.forEach((rule, i) => {
        rule.classList.toggle("is-now", i === idx);
        rule.classList.toggle("is-debris", i < idx && i >= 0);
      });
    },
    still() {
      cam("still", 1.12, 0, 0);
    },
    return(p) {
      const colo = document.getElementById("colo") as HTMLElement;
      colo.style.opacity = p < 0.72 ? "1" : String(lerp(1, 0.2, ramp(p, 0.72, 1)));
    },
  };

  const draw = (now: number) => {
    const live = acts.filter((item) => item.active);
    if (live.length) shown = live[live.length - 1];
    else {
      const y = window.scrollY + 8;
      for (const item of acts) if (item.el.offsetTop <= y) shown = item;
    }
    const act = shown;
    for (const item of acts) item.el.classList.toggle("is-cover", item === act);
    render[act.id](act.p);
    battle.setAct(act.id, act.p);

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
    if (!fx.holding) shade.style.opacity = "0";

    const paper = act.id === "still" || (act.id === "kakoi" && act.p >= 0.34);
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
