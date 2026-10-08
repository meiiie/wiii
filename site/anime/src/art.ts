/**
 * Plates are chosen by rendered width × devicePixelRatio × the camera's max scale.
 * `sizes` on each picture already carries the scale. 1920 and 2560 files are
 * appended when they answer, so a later super-resolution drop needs no markup edit.
 */

const probe = (url: string) =>
  new Promise<boolean>((resolve) => {
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = url;
  });

const stemOf = (url: string) => url.trim().split(/\s+/)[0].replace(/-\d+\.(webp|avif)$/, "");

const extend = (srcset: string, widths: number[], ext: string) => {
  const stem = stemOf(srcset.split(",")[0] ?? "");
  if (!stem) return srcset;
  const extra = widths
    .filter((w) => !srcset.includes(` ${w}w`))
    .map((w) => `${stem}-${w}.${ext} ${w}w`)
    .join(", ");
  return extra ? `${srcset}, ${extra}` : srcset;
};

export async function upgradeArt(): Promise<void> {
  const webp: number[] = [];
  if (await probe("/art/kf01_awaken-1920.webp")) webp.push(1920);
  if (await probe("/art/kf01_awaken-2560.webp")) webp.push(2560);
  const avif: number[] = [];
  if (webp.includes(1920) && (await probe("/art/kf01_awaken-1920.avif"))) avif.push(1920);
  if (webp.includes(2560) && (await probe("/art/kf01_awaken-2560.avif"))) avif.push(2560);
  const cuts: number[] = [];
  if (await probe("/art/cut-wiii-1920.webp")) cuts.push(1920);
  if (await probe("/art/cut-wiii-2560.webp")) cuts.push(2560);

  if (webp.length || avif.length) {
    document.querySelectorAll<HTMLSourceElement | HTMLImageElement>("source[srcset], img[srcset]").forEach((node) => {
      const set = node.getAttribute("srcset") ?? "";
      if (set.includes("/art/cut-")) return;
      if (set.includes(".avif") && avif.length) node.setAttribute("srcset", extend(set, avif, "avif"));
      else if (set.includes(".webp") && webp.length) node.setAttribute("srcset", extend(set, webp, "webp"));
    });
    const hi = webp.includes(2560) ? 2560 : 1920;
    document.querySelectorAll<HTMLElement>(".shards i").forEach((el) => {
      el.style.backgroundImage = `url("/art/kf04_impact-${hi}.webp")`;
    });
  }

  if (cuts.length) {
    document.querySelectorAll<HTMLImageElement>("img[srcset]").forEach((img) => {
      const set = img.getAttribute("srcset") ?? "";
      if (!set.includes("/art/cut-")) return;
      img.setAttribute("srcset", extend(set, cuts, "webp"));
    });
  }
}
