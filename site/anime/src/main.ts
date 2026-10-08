import "@fontsource/anton/latin-400.css";
import "@fontsource/anton/latin-ext-400.css";
import "@fontsource/anton/vietnamese-400.css";
import "@fontsource/dm-mono/400.css";
import "@fontsource/instrument-sans/400.css";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "./style.css";
import { paintStillSnow } from "./weather";

function paintGrain(): void {
  const grain = document.getElementById("grain");
  if (!grain) return;
  const canvas = document.createElement("canvas");
  canvas.width = 140;
  canvas.height = 140;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const image = ctx.createImageData(140, 140);
  for (let i = 0; i < image.data.length; i += 4) {
    const n = 140 + Math.random() * 115;
    image.data[i] = n;
    image.data[i + 1] = n;
    image.data[i + 2] = n;
    image.data[i + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);
  grain.style.backgroundImage = `url(${canvas.toDataURL("image/png")})`;
}

paintGrain();

const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
const coarse = window.matchMedia("(pointer: coarse), (hover: none)");
const markCoarse = () => document.documentElement.classList.toggle("is-coarse", coarse.matches);
markCoarse();
coarse.addEventListener("change", markCoarse);

async function boot(): Promise<void> {
  if (reduced.matches) {
    document.documentElement.classList.add("is-reduced");
    const snow = document.getElementById("snow") as HTMLCanvasElement | null;
    if (snow) paintStillSnow(snow);
    return;
  }
  document.documentElement.classList.add("is-motion");
  const { start } = await import("./director");
  await start();
}

void boot();

reduced.addEventListener("change", () => {
  window.location.reload();
});
