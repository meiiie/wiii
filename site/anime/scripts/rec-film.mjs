/**
 * Virtual-clock recording of /film plus a phone contact sheet of the 8 portrait plates.
 * The page clock is stepped with __WIII.present so the run does not depend on wall time.
 */
import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const port = 4193;
const chrome = process.env.CHROME_PATH || "/usr/local/bin/google-chrome";
const out = process.env.FILM_OUT || "/opt/cursor/artifacts";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const STOPS = [
  ["act-awaken", 0.85, "kf01_awaken", "00 Awaken"],
  ["act-intrusion", 0.8, "kf02_intrusion", "01 Intrusion"],
  ["act-clash", 0.2, "kf03_clash", "02 Clash"],
  ["act-clash", 0.75, "kf04_impact", "02 Impact"],
  ["act-observe", 0.5, "kf05_observe", "03 Observe"],
  ["act-neko", 0.75, "kf06_neko_burst", "04 Neko"],
  ["act-kakoi", 0.85, "kf07_kakoi", "05 Kakoi"],
  ["act-still", 0.5, "kf08_still", "06 Still"],
];

const preview = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
  cwd: root,
  stdio: ["ignore", "pipe", "pipe"],
});
const waitForServer = async () => {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(`http://127.0.0.1:${port}/film`)).ok) return;
    } catch { /* booting */ }
    await sleep(200);
  }
  throw new Error("preview did not start");
};
await waitForServer();

mkdirSync(`${out}/screenshots`, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: "new",
  args: ["--no-sandbox", "--hide-scrollbars"],
});
const page = await browser.newPage();

const show = async (id, t, file) => {
  for (let i = 0; i < 40; i++) {
    const plate = await page.evaluate((act, local) => {
      window.__WIII.scrollToAct(act, local);
      return window.__WIII.plate || "";
    }, id, t);
    if (plate.includes(file)) return plate;
    await sleep(80);
  }
  return page.evaluate(() => window.__WIII.plate || "");
};

const film = async (w, h, dpr, fps, name) => {
  await page.setViewport({ width: w, height: h, deviceScaleFactor: dpr, isMobile: w < 800, hasTouch: w < 800 });
  await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__WIII?.present, { timeout: 15000 });
  await sleep(300);
  const dir = `/tmp/${name}`;
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const frames = Math.round(14.2 * fps);
  for (let i = 0; i <= frames; i++) {
    const u = i / frames;
    await page.evaluate((t) => window.__WIII.present(t), u);
    if (i % 8 === 0) {
      await page.waitForFunction(() => (window.__WIII.debug().textures.length > 2), { timeout: 8000 }).catch(() => {});
      await page.evaluate((t) => window.__WIII.present(t), u);
    }
    await page.screenshot({ path: `${dir}/f${String(i).padStart(4, "0")}.jpg`, type: "jpeg", quality: 72 });
    if (i % 20 === 0) console.log(`${name} ${i}/${frames}`);
  }
  execFileSync("ffmpeg", [
    "-y", "-framerate", String(fps), "-i", `${dir}/f%04d.jpg`,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    `${out}/${name}.mp4`,
  ], { stdio: "inherit" });
  console.log("wrote", `${out}/${name}.mp4`);
};

try {
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await page.goto(`http://127.0.0.1:${port}/film`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__WIII?.plate, { timeout: 15000 });
  const shots = [];
  for (let i = 0; i < STOPS.length; i++) {
    const [id, t, file, label] = STOPS[i];
    const plate = await show(id, t, file);
    const path = `${out}/screenshots/portrait-${String(i).padStart(2, "0")}.png`;
    await page.screenshot({ path });
    shots.push({ path, label, plate });
    console.log("shot", label, plate);
  }
  const compose = `
from PIL import Image, ImageDraw, ImageFont
shots = ${JSON.stringify(shots)}
cell = (195, 422)
cols, rows, label_h, pad = 4, 2, 22, 8
sheet = Image.new("RGB", (cols*cell[0]+(cols+1)*pad, rows*(cell[1]+label_h)+(rows+1)*pad), (12,12,14))
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
for i, shot in enumerate(shots):
    im = Image.open(shot["path"]).convert("RGB").resize(cell, Image.Resampling.LANCZOS)
    c, r = i % cols, i // cols
    x, y = pad + c*(cell[0]+pad), pad + r*(cell[1]+label_h+pad)
    sheet.paste(im, (x, y))
    draw.text((x+3, y+cell[1]+3), shot["label"], fill=(243,238,227), font=font)
sheet.save(${JSON.stringify(`${out}/screenshots/film-portrait-contact.png`)})
print("contact", sheet.size)
`;
  execFileSync("python3", ["-c", compose], { stdio: "inherit" });
  await film(390, 844, 2, 8, "film-390");
  await film(1440, 900, 1, 8, "film-1440");
} finally {
  await browser.close();
  preview.kill("SIGTERM");
}
