/** Capability gate for the film engine. The DOM page stays up when this returns false. */

export function hasWebGL2(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2"));
  } catch {
    return false;
  }
}

export function isSoftwareRenderer(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2");
    if (!gl) return true;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    return /swiftshader|llvmpipe|softpipe|software|subzero/i.test(renderer);
  } catch {
    return true;
  }
}

export function isLowTier(): boolean {
  const nav = navigator as Navigator & { deviceMemory?: number; connection?: { saveData?: boolean } };
  if (nav.connection?.saveData) return true;
  if (typeof nav.deviceMemory === "number" && nav.deviceMemory <= 2) return true;
  if (navigator.hardwareConcurrency > 0 && navigator.hardwareConcurrency <= 2) return true;
  return false;
}

/** Real GPUs with motion allowed. Software GL and the low tier keep the DOM page. */
export function shouldUseFilm(): boolean {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (!hasWebGL2()) return false;
  if (isLowTier()) return false;
  if (isSoftwareRenderer()) return false;
  return true;
}
