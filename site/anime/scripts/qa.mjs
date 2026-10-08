/**
 * Rest-stop QA for the anime showcase.
 *
 * For each rest stop at 1280x800, 1440x900, and 390x844, with the pointer at
 * the center and at a corner:
 *  (a) sample every visible text box; fail if a decorative layer is above it
 *  (b) fail if a [data-drift] layer is visible after the Kakoi seal
 *  (c) fail if text is under 16px on mobile or secondary text is under 18px
 *  (d) write a contact sheet per viewport
 *
 * Decorative layers use pointer-events: none, which elementsFromPoint skips.
 * The check forces pointer-events: auto first so a layer cannot hide that way.
 */
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = resolve(root, "qa-out");
const port = 4179;
const chrome = process.env.CHROME_PATH || "/usr/local/bin/google-chrome";

const STOPS = [
  { id: "act-awaken", p: 0, name: "00 Awaken", sealed: false },
  { id: "act-intrusion", p: 0.33, name: "01 Intrusion", sealed: false },
  { id: "act-clash", p: 0.4, name: "02 Clash", sealed: false },
  { id: "act-observe", p: 0.44, name: "03 Observe", sealed: false },
  { id: "act-neko", p: 0.25, name: "04 Neko wait", sealed: false },
  { id: "act-neko", p: 0.75, name: "04 Neko burst", sealed: false },
  { id: "act-kakoi", p: 0.167, name: "05 Ring", sealed: false },
  { id: "act-kakoi", p: 0.5, name: "05 Harness", sealed: true },
  { id: "act-kakoi", p: 0.833, name: "05 Later rule", sealed: true },
  { id: "act-still", p: 0.45, name: "06 Still", sealed: true },
  { id: "act-return", p: 0.29, name: "07 Return", sealed: true },
  { id: "colophon", p: 1, name: "Colophon", sealed: true },
];

const VIEWPORTS = [
  { w: 1280, h: 800, mobile: false },
  { w: 1440, h: 900, mobile: false },
  { w: 390, h: 844, mobile: true },
];

mkdirSync(outDir, { recursive: true });

const preview = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
  cwd: root,
  stdio: ["ignore", "pipe", "pipe"],
});
let previewLog = "";
preview.stdout.on("data", (chunk) => { previewLog += chunk; });
preview.stderr.on("data", (chunk) => { previewLog += chunk; });

const waitForServer = async () => {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/`);
      if (res.ok) return;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`preview did not start\n${previewLog}`);
};

await waitForServer();

const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: "new",
  args: ["--no-sandbox", "--hide-scrollbars"],
});
const page = await browser.newPage();
const pageErrors = [];
page.on("pageerror", (err) => pageErrors.push(String(err)));

const failures = [];
const fail = (msg) => {
  failures.push(msg);
  console.error("FAIL", msg);
};

const inspect = () => {
  const force = document.querySelectorAll("[data-decor], [data-drift], canvas");
  for (const el of force) el.style.setProperty("pointer-events", "auto", "important");
  const visible = (el) => {
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (Number(style.opacity) < 0.05) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return false;
    if (rect.bottom < 4 || rect.right < 0 || rect.top > innerHeight || rect.left > innerWidth) return false;
    return true;
  };
  const texts = [...document.querySelectorAll("h1, h2, p, a, button, li, em, strong, span")]
    .filter((el) => !el.closest(".sr"))
    .filter((el) => (el.innerText || "").trim().length > 0)
    .filter(visible);
  for (const el of texts) el.style.setProperty("pointer-events", "auto", "important");
  const covers = [];
  for (const el of texts) {
    const rect = el.getBoundingClientRect();
    for (const [fx, fy] of [[0.2, 0.35], [0.5, 0.5], [0.8, 0.65]]) {
      const x = Math.min(innerWidth - 2, Math.max(1, rect.left + rect.width * fx));
      const y = Math.min(innerHeight - 2, Math.max(1, rect.top + rect.height * fy));
      if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) continue;
      const stack = document.elementsFromPoint(x, y);
      const textAt = stack.findIndex((node) => node === el || el.contains(node));
      if (textAt < 0) continue;
      const decor = stack.slice(0, textAt).map((node) => node.closest("[data-decor], [data-drift], canvas")).find((node) => node && !el.contains(node));
      if (decor) {
        covers.push({
          text: (el.innerText || "").trim().slice(0, 48),
          tag: el.tagName.toLowerCase(),
          cover: decor.id || decor.className?.toString?.().slice(0, 60) || decor.tagName,
          x: Math.round(x),
          y: Math.round(y),
        });
        break;
      }
    }
  }
  const drift = [...document.querySelectorAll("[data-drift]")].filter(visible).map((el) => el.id || el.className.toString().slice(0, 40));
  const small = texts
    .filter((el) => {
      const size = Number.parseFloat(getComputedStyle(el).fontSize);
      const secondary = !["H1", "H2"].includes(el.tagName) && !el.closest(".ono, .tate");
      if (innerWidth <= 800) return size < 16;
      return secondary && size < 18;
    })
    .map((el) => ({
      text: (el.innerText || "").trim().slice(0, 40),
      tag: el.tagName.toLowerCase(),
      size: Number.parseFloat(getComputedStyle(el).fontSize),
    }));
  return {
    sealed: document.documentElement.classList.contains("is-sealed"),
    covers,
    drift,
    small,
  };
};

try {
  for (const vp of VIEWPORTS) {
    await page.setViewport({ width: vp.w, height: vp.h, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle0" });
    await page.waitForFunction(() => window.__WIII?.scrollToAct);
    const shots = [];
    for (const stop of STOPS) {
      await page.evaluate((id, p) => {
        if (id === "colophon") {
          window.__WIII.lenis.scrollTo(document.documentElement.scrollHeight, { immediate: true, force: true });
          return;
        }
        window.__WIII.scrollToAct(id, p);
      }, stop.id, stop.p);
      await new Promise((r) => setTimeout(r, 180));
      const points = [
        { name: "center", x: vp.w / 2, y: vp.h / 2 },
        { name: "corner", x: 28, y: 28 },
      ];
      let shot = false;
      for (const point of points) {
        await page.mouse.move(point.x, point.y);
        await new Promise((r) => setTimeout(r, 80));
        const result = await page.evaluate(inspect);
        if (!shot && point.name === "center") {
          const file = `${outDir}/${vp.w}-${String(shots.length).padStart(2, "0")}.png`;
          await page.screenshot({ path: file });
          shots.push(file);
          shot = true;
        }
        const where = `${vp.w}x${vp.h} ${stop.name} @${point.name}`;
        if (result.sealed !== stop.sealed) fail(`${where}: sealed=${result.sealed}, expected ${stop.sealed}`);
        for (const cover of result.covers) fail(`${where}: "${cover.text}" covered by ${cover.cover} at ${cover.x},${cover.y}`);
        if (stop.sealed && result.drift.length) fail(`${where}: drift still visible: ${result.drift.join(", ")}`);
        for (const item of result.small) fail(`${where}: ${item.tag} "${item.text}" is ${item.size}px`);
      }
    }
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const overflowOf = () => page.evaluate(() => {
    const root = document.documentElement;
    const cw = root.clientWidth;
    const offenders = [...document.querySelectorAll("body *")]
      .map((el) => {
        const rect = el.getBoundingClientRect();
        return { el, rect };
      })
      .filter(({ rect }) => rect.width > 2 && (rect.right > cw + 1 || rect.left < -1))
      .slice(0, 6)
      .map(({ el, rect }) => `${el.tagName}#${el.id}.${String(el.className).slice(0, 24)} right=${Math.round(rect.right)} w=${Math.round(rect.width)}`);
    return { sw: root.scrollWidth, cw, offenders };
  });
  const ratiosOf = () => page.evaluate(() => {
    const bad = [];
    for (const img of document.images) {
      if (!img.complete || !img.naturalWidth || !img.naturalHeight) continue;
      const style = getComputedStyle(img);
      if (style.display === "none" || style.visibility === "hidden") continue;
      if (style.objectFit === "cover") continue;
      if (Number(style.opacity) < 0.05) continue;
      const w = img.offsetWidth;
      const h = img.offsetHeight;
      if (w < 8 || h < 8) continue;
      const natural = img.naturalWidth / img.naturalHeight;
      const rendered = w / h;
      if (Math.abs(rendered - natural) / natural > 0.02) {
        bad.push(`${img.id || img.alt.slice(0, 24)} ${rendered.toFixed(3)} vs ${natural.toFixed(3)} fit=${style.objectFit}`);
      }
    }
    return bad;
  });
  const drag = async (client, x, y0, y1) => {
    await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: y0, id: 1 }] });
    const steps = 5;
    for (let i = 1; i <= steps; i++) {
      await client.send("Input.dispatchTouchEvent", {
        type: "touchMove",
        touchPoints: [{ x, y: Math.round(y0 + ((y1 - y0) * i) / steps), id: 1 }],
      });
      await sleep(12);
    }
    await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await sleep(30);
  };

  for (const vp of [
    { w: 390, h: 844, dpr: 2 },
    { w: 360, h: 780, dpr: 3 },
  ]) {
    await page.setViewport({ width: vp.w, height: vp.h, deviceScaleFactor: vp.dpr, isMobile: true, hasTouch: true });
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle0" });
    await page.waitForFunction(() => window.__WIII?.scrollToAct);
    await sleep(250);
    const client = await page.createCDPSession();
    const before = await page.evaluate(() => window.__WIII.strikes);
    await page.evaluate(() => window.__WIII.scrollToAct("act-awaken", 0));
    await sleep(120);
    const y0 = vp.h * 0.72;
    const y1 = vp.h * 0.28;
    for (let i = 0; i < 20; i++) await drag(client, vp.w / 2, y0, y1);
    await sleep(400);
    const mid = await page.evaluate(() => window.scrollY);
    if (mid < 200) fail(`${vp.w} touch drags did not scroll (scrollY=${Math.round(mid)})`);
    for (let i = 0; i < 20; i++) await drag(client, vp.w / 2, y1, y0);
    await sleep(500);
    const back = await page.evaluate(() => window.scrollY);
    if (back > 160) fail(`${vp.w} return flings left scrollY=${Math.round(back)}`);
    const gestureScroll = async (yDistance) => {
      const before = await page.evaluate(() => window.scrollY);
      const send = (source) => client.send("Input.synthesizeScrollGesture", {
        x: vp.w / 2,
        y: vp.h / 2,
        yDistance,
        speed: source === "touch" ? 2500 : 1200,
        gestureSourceType: source,
      });
      await send("touch");
      await sleep(400);
      let after = await page.evaluate(() => window.scrollY);
      if (Math.abs(after - before) < 40) {
        // Headless Chrome drops touch-source compositor gestures even on a
        // plain document. Mouse-source gestures use the same scroll chain.
        await send("mouse");
        await sleep(500);
        after = await page.evaluate(() => window.scrollY);
        console.log(`${vp.w} touch-source gesture was a no-op; mouse-source ${Math.round(before)} -> ${Math.round(after)}`);
      }
      return { before, after };
    };
    const gesture = await gestureScroll(-500);
    if (Math.abs(gesture.after - gesture.before) < 40) {
      fail(`${vp.w} synthesizeScrollGesture did not move scroll (${Math.round(gesture.before)} -> ${Math.round(gesture.after)})`);
    }
    await gestureScroll(700);
    const afterSwipes = await page.evaluate(() => ({
      strikes: window.__WIII.strikes,
      wind: document.documentElement.classList.contains("is-wind"),
      charge: document.documentElement.classList.contains("is-charge"),
    }));
    if (afterSwipes.strikes !== before) fail(`${vp.w} swipes triggered ${afterSwipes.strikes - before} strikes`);
    if (afterSwipes.wind || afterSwipes.charge) fail(`${vp.w} swipe left wind/charge stuck`);
    const tapAt = await page.evaluate(() => window.__WIII.strikes);
    await page.touchscreen.tap(vp.w * 0.5, vp.h * 0.55);
    await sleep(250);
    const tapped = await page.evaluate(() => window.__WIII.strikes);
    if (tapped <= tapAt) fail(`${vp.w} tap did not strike (${tapAt} -> ${tapped})`);
    const flow = await overflowOf();
    if (flow.sw > flow.cw + 1) fail(`${vp.w} overflow scrollWidth=${flow.sw} client=${flow.cw} ${flow.offenders.join(" | ")}`);
    for (const id of ["act-awaken", "act-intrusion", "act-clash", "act-observe", "act-neko", "act-kakoi", "act-still", "act-return"]) {
      await page.evaluate((actId) => window.__WIII.scrollToAct(actId, 0.3), id);
      const name = id.replace("act-", "");
      try {
        await page.waitForFunction((actName) => document.documentElement.dataset.act === actName, { timeout: 1500 }, name);
      } catch {
        const act = await page.evaluate(() => document.documentElement.dataset.act);
        fail(`${vp.w} could not reach ${id} (at ${act})`);
      }
      const box = await overflowOf();
      if (box.sw > box.cw + 1) fail(`${vp.w} ${id} overflow ${box.sw}>${box.cw} ${box.offenders.join(" | ")}`);
    }
    await page.evaluate(() => window.__WIII.scrollToAct("act-intrusion", 0.33));
    await sleep(200);
    const ratios = await ratiosOf();
    for (const item of ratios) fail(`${vp.w} image ratio ${item}`);
    await page.mouse.move(vp.w / 2, vp.h / 2);
    const covered = await page.evaluate(inspect);
    for (const cover of covered.covers) fail(`${vp.w} touch rest "${cover.text}" covered by ${cover.cover}`);
    const flashes = await page.evaluate(() => window.__WIII.flashTimes);
    for (let i = 0; i < flashes.length; i++) {
      const burst = flashes.filter((t) => t >= flashes[i] && t < flashes[i] + 1000).length;
      if (burst > 3) {
        fail(`${vp.w} ${burst} flashes inside 1s`);
        break;
      }
    }
    if (vp.w === 390) {
      await client.send("Emulation.setCPUThrottlingRate", { rate: 4 });
      await page.evaluate(() => window.__WIII.scrollToAct("act-intrusion", 0.4));
      await sleep(200);
      const frame = await page.evaluate(() => new Promise((resolve) => {
        let frames = 0;
        const t0 = performance.now();
        const loop = (now) => {
          frames += 1;
          if (now - t0 < 2000) requestAnimationFrame(loop);
          else resolve({ frames, ms: (now - t0) / frames });
        };
        requestAnimationFrame(loop);
      }));
      console.log(`perf 390x844 4xCPU frames=${frame.frames} avg=${frame.ms.toFixed(2)}ms`);
      if (frame.ms > 50) fail(`390 throttled frame time ${frame.ms.toFixed(1)}ms`);
      await client.send("Emulation.setCPUThrottlingRate", { rate: 1 });
    }
    await client.detach();
  }
} finally {
  await browser.close();
  preview.kill("SIGTERM");
}

if (pageErrors.length) {
  for (const err of pageErrors) fail(`pageerror ${err}`);
}

const compose = `
from PIL import Image, ImageDraw, ImageFont
import os
out = ${JSON.stringify(outDir)}
names = ${JSON.stringify(STOPS.map((s) => s.name))}
for label, cell in (("1280", (420, 262)), ("1440", (420, 262)), ("390", (160, 346))):
    cols, rows, label_h, pad = 4, 3, 20, 8
    sheet = Image.new("RGB", (cols*cell[0]+(cols+1)*pad, rows*(cell[1]+label_h)+(rows+1)*pad), (12,12,14))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    for i, name in enumerate(names):
        path = os.path.join(out, f"{label}-{i:02d}.png")
        if not os.path.exists(path):
            continue
        im = Image.open(path).convert("RGB").resize(cell, Image.Resampling.LANCZOS)
        c, r = i % cols, i // cols
        x, y = pad + c*(cell[0]+pad), pad + r*(cell[1]+label_h+pad)
        sheet.paste(im, (x, y))
        draw.text((x+3, y+cell[1]+2), f"{i} {name}", fill=(243,238,227), font=font)
    sheet.save(os.path.join(out, f"contact-{label}.png"))
    print("sheet", label, sheet.size)
`;
writeFileSync(`${outDir}/compose.py`, compose);
execFileSync("python3", [`${outDir}/compose.py`], { stdio: "inherit" });

console.log(failures.length ? `\n${failures.length} failure(s)` : "\nQA passed");
if (failures.length) process.exit(1);
