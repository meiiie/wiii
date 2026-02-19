/**
 * Face geometry generation — Sprint 129: SVG Face on Blob.
 * Sprint 130: Eye shine, blush ellipses, happy eye arcs.
 * Sprint 131: Kawaii Phase 1 — anime eyes (iris/clipPath), nose, blush hash lines.
 * Generates SVG paths/positions for eyes, mouth, and eyebrows
 * relative to the blob center and radius.
 */

/** Computed dimensions for all face features, relative to blob */
export interface FaceDimensions {
  /** Distance from center to each eye center (horizontal) */
  eyeSpacing: number;
  /** Eye vertical position (negative = above center) */
  eyeY: number;
  /** Eye (sclera) horizontal radius */
  eyeRx: number;
  /** Eye (sclera) vertical radius (base — modified by eyeOpenness) */
  eyeRy: number;
  /** Pupil radius (base — modified by pupilSize) */
  pupilR: number;
  /** Max pupil offset from eye center */
  pupilMaxOffset: number;
  /** Eyebrow Y position (above eyes) */
  browY: number;
  /** Eyebrow half-width */
  browHalfWidth: number;
  /** Eyebrow stroke width */
  browStroke: number;
  /** Mouth Y position (below center) */
  mouthY: number;
  /** Mouth base width */
  mouthBaseWidth: number;
  /** Mouth stroke width */
  mouthStroke: number;

  // Sprint 130: Eye shine highlights (Ghibli style)
  /** Primary highlight radius */
  shineR1: number;
  /** Secondary highlight radius */
  shineR2: number;
  /** Primary highlight X offset from eye center */
  shineOffsetX1: number;
  /** Primary highlight Y offset from eye center */
  shineOffsetY1: number;
  /** Secondary highlight X offset from eye center */
  shineOffsetX2: number;
  /** Secondary highlight Y offset from eye center */
  shineOffsetY2: number;

  // Sprint 130: Blush ellipses
  /** Blush X offset from center (distance to each cheek) */
  blushX: number;
  /** Blush Y position (below eyes) */
  blushY: number;
  /** Blush horizontal radius */
  blushRx: number;
  /** Blush vertical radius */
  blushRy: number;

  // Sprint 131: Colored iris (anime eye layer between sclera and pupil)
  /** Iris horizontal radius (smaller than sclera) */
  irisRx: number;
  /** Iris vertical radius (smaller than sclera) */
  irisRy: number;

  // Sprint 131: Nose (minimal dot)
  /** Nose Y position (between eyes and mouth) */
  noseY: number;
  /** Nose radius (tiny dot) */
  noseR: number;

  // Sprint 131: Blush hash lines (anime diagonal strokes ///)
  /** Hash line length */
  blushHashLen: number;
  /** Horizontal gap between hash lines */
  blushHashGap: number;
  /** Hash line stroke width */
  blushHashStroke: number;
}

/**
 * Compute face feature dimensions from blob radius.
 * All values are proportional to blobRadius for size-adaptive rendering.
 */
export function getFaceDimensions(blobRadius: number): FaceDimensions {
  const faceScale = blobRadius * 0.82;
  return {
    // Sprint 131: Anime proportions — larger eyes, closer spacing
    eyeSpacing: faceScale * 0.28,
    eyeY: -faceScale * 0.06,
    eyeRx: faceScale * 0.22,
    eyeRy: faceScale * 0.27,
    pupilR: faceScale * 0.09,
    pupilMaxOffset: faceScale * 0.08,
    browY: -faceScale * 0.38,
    browHalfWidth: faceScale * 0.18,
    browStroke: Math.max(1.5, faceScale * 0.055),
    mouthY: faceScale * 0.28,
    mouthBaseWidth: faceScale * 0.36,
    mouthStroke: Math.max(1.5, faceScale * 0.05),

    // Sprint 131: Bigger Ghibli-style highlights for anime eyes
    shineR1: faceScale * 0.060,
    shineR2: faceScale * 0.035,
    shineOffsetX1: -faceScale * 0.07,
    shineOffsetY1: -faceScale * 0.08,
    shineOffsetX2: faceScale * 0.05,
    shineOffsetY2: faceScale * 0.05,

    // Blush ellipses: below eyes, slightly outward
    blushX: faceScale * 0.30,
    blushY: faceScale * 0.12,
    blushRx: faceScale * 0.12,
    blushRy: faceScale * 0.07,

    // Sprint 131: Colored iris (75-80% of sclera size)
    irisRx: faceScale * 0.17,
    irisRy: faceScale * 0.22,

    // Sprint 131: Nose (tiny dot between eyes and mouth)
    noseY: faceScale * 0.12,
    noseR: faceScale * 0.022,

    // Sprint 131: Blush hash lines (3 diagonal strokes per cheek)
    blushHashLen: faceScale * 0.06,
    blushHashGap: faceScale * 0.025,
    blushHashStroke: Math.max(0.8, faceScale * 0.02),
  };
}

/** Input shape for mouth path generation */
export interface MouthShape {
  /** -1 (frown) to 1 (smile) */
  curve: number;
  /** 0 (closed) to 1 (fully open) */
  openness: number;
  /** 0.5 (narrow) to 1.5 (wide) */
  width: number;
}

/**
 * Generate an SVG path for the mouth using cubic bezier curves.
 *
 * @param cx - Horizontal center
 * @param cy - Vertical center of mouth
 * @param shape - Mouth expression parameters
 * @param baseWidth - Base mouth width from FaceDimensions
 * @returns SVG path `d` string
 */
export function generateMouthPath(
  cx: number,
  cy: number,
  shape: MouthShape,
  baseWidth: number,
): string {
  const hw = (baseWidth / 2) * shape.width;
  const curveY = shape.curve * baseWidth * 0.4;

  // Upper lip (or full mouth when closed)
  const left = cx - hw;
  const right = cx + hw;
  const cpLeftX = cx - hw * 0.5;
  const cpRightX = cx + hw * 0.5;

  const upper = `M ${left.toFixed(1)} ${cy.toFixed(1)} C ${cpLeftX.toFixed(1)} ${(cy + curveY).toFixed(1)}, ${cpRightX.toFixed(1)} ${(cy + curveY).toFixed(1)}, ${right.toFixed(1)} ${cy.toFixed(1)}`;

  if (shape.openness < 0.05) return upper;

  // Lower lip — forms closed shape when mouth is open
  const openY = shape.openness * baseWidth * 0.35;
  const lower = ` C ${cpRightX.toFixed(1)} ${(cy + curveY + openY).toFixed(1)}, ${cpLeftX.toFixed(1)} ${(cy + curveY + openY).toFixed(1)}, ${left.toFixed(1)} ${cy.toFixed(1)} Z`;

  return upper + lower;
}

/**
 * Sprint 131 Phase 2: Generate a cat mouth ω path.
 * Two small upward bumps with a center dip — the quintessential kawaii idle mouth.
 */
export function generateCatMouthPath(
  cx: number,
  cy: number,
  baseWidth: number,
  widthMul: number,
): string {
  const hw = (baseWidth / 2) * widthMul;
  const bump = baseWidth * 0.15;
  const dip = baseWidth * 0.04;
  const left = cx - hw;
  const right = cx + hw;
  return `M ${left.toFixed(1)} ${cy.toFixed(1)} Q ${(cx - hw * 0.5).toFixed(1)} ${(cy - bump).toFixed(1)}, ${cx.toFixed(1)} ${(cy + dip).toFixed(1)} Q ${(cx + hw * 0.5).toFixed(1)} ${(cy - bump).toFixed(1)}, ${right.toFixed(1)} ${cy.toFixed(1)}`;
}

/**
 * Sprint 131 Phase 2: Generate a dot mouth · path.
 * Tiny filled circle — contemplative, quiet thinking.
 */
export function generateDotMouthPath(
  cx: number,
  cy: number,
  baseWidth: number,
): string {
  const r = baseWidth * 0.08;
  return `M ${cx.toFixed(1)} ${(cy - r).toFixed(1)} A ${r.toFixed(1)} ${r.toFixed(1)} 0 1 1 ${cx.toFixed(1)} ${(cy + r).toFixed(1)} A ${r.toFixed(1)} ${r.toFixed(1)} 0 1 1 ${cx.toFixed(1)} ${(cy - r).toFixed(1)} Z`;
}

/**
 * Sprint 131 Phase 2: Generate a wavy mouth ～ path.
 * Nervous/worried sine wave — used for error state.
 */
export function generateWavyMouthPath(
  cx: number,
  cy: number,
  baseWidth: number,
  widthMul: number,
): string {
  const hw = (baseWidth / 2) * widthMul;
  const wave = baseWidth * 0.08;
  const left = cx - hw;
  const right = cx + hw;
  const t = hw * 2 / 3;
  return `M ${left.toFixed(1)} ${cy.toFixed(1)} C ${(left + t * 0.5).toFixed(1)} ${(cy - wave).toFixed(1)}, ${(left + t).toFixed(1)} ${(cy + wave).toFixed(1)}, ${cx.toFixed(1)} ${cy.toFixed(1)} C ${(cx + t * 0.5).toFixed(1)} ${(cy - wave).toFixed(1)}, ${(right - t * 0.5).toFixed(1)} ${(cy + wave).toFixed(1)}, ${right.toFixed(1)} ${cy.toFixed(1)}`;
}

/**
 * Sprint 144: Generate a pout/kiss mouth ε path.
 * Small puckered circle — used for pouting, kissing, playful displeasure.
 * Kaomoji: (ε), (3), chu~
 */
export function generatePoutMouthPath(
  cx: number,
  cy: number,
  baseWidth: number,
  widthMul: number,
): string {
  // Small puckered circle, slightly off-center forward
  const r = baseWidth * 0.12 * widthMul;
  const bulge = r * 0.3; // slight horizontal protrusion (ε shape)
  // Draw a rounded pout: left half is a tight curve, right half bulges out
  return `M ${(cx - r).toFixed(1)} ${cy.toFixed(1)} Q ${(cx - r * 0.5).toFixed(1)} ${(cy - r).toFixed(1)}, ${cx.toFixed(1)} ${(cy - r * 0.7).toFixed(1)} Q ${(cx + r * 0.5 + bulge).toFixed(1)} ${(cy - r * 0.3).toFixed(1)}, ${(cx + r * 0.3 + bulge).toFixed(1)} ${cy.toFixed(1)} Q ${(cx + r * 0.5 + bulge).toFixed(1)} ${(cy + r * 0.3).toFixed(1)}, ${cx.toFixed(1)} ${(cy + r * 0.7).toFixed(1)} Q ${(cx - r * 0.5).toFixed(1)} ${(cy + r).toFixed(1)}, ${(cx - r).toFixed(1)} ${cy.toFixed(1)} Z`;
}

/**
 * Sprint 144: Generate knocked-out eye X path (× ×).
 * Two crossed lines forming an X — used for error/KO states.
 * Kaomoji: (×_×), (X_X)
 */
export function generateKnockedOutEyePath(cx: number, cy: number, r: number): string {
  const s = r * 0.6; // half-size of the X
  return `M ${(cx - s).toFixed(1)} ${(cy - s).toFixed(1)} L ${(cx + s).toFixed(1)} ${(cy + s).toFixed(1)} M ${(cx + s).toFixed(1)} ${(cy - s).toFixed(1)} L ${(cx - s).toFixed(1)} ${(cy + s).toFixed(1)}`;
}

/**
 * Sprint 143: Generate a 4-pointed star path for star pupil overlay ★.
 * Smaller, filled version of the sparkle — centered on pupil position.
 */
export function generateStarPupilPath(cx: number, cy: number, r: number): string {
  const innerR = r * 0.4;
  const points: string[] = [];
  for (let i = 0; i < 8; i++) {
    const angle = (i * Math.PI) / 4 - Math.PI / 2; // start at top
    const radius = i % 2 === 0 ? r : innerR;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    points.push(`${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`);
  }
  points.push("Z");
  return points.join(" ");
}

/**
 * Sprint 143: Generate a small heart path for heart pupil overlay ♥.
 * Centered on pupil position, used during "doki" micro-reaction.
 */
export function generateHeartPupilPath(cx: number, cy: number, r: number): string {
  const w = r * 0.9;
  const h = r;
  const top = cy - h * 0.3;
  const bottom = cy + h * 0.7;
  return [
    `M ${cx} ${bottom}`,
    `C ${cx - w * 1.4} ${cy}, ${cx - w * 0.5} ${top - h * 0.4}, ${cx} ${top + h * 0.1}`,
    `C ${cx + w * 0.5} ${top - h * 0.4}, ${cx + w * 1.4} ${cy}, ${cx} ${bottom}`,
    "Z",
  ].join(" ");
}

// ─── Sprint 143b: New Manga Indicator SVG Generators ──────────────────────

/**
 * Sprint 143b: Generate a manga anger vein 💢 — classic cross-shaped bulge mark.
 * Four curved lobes arranged in a plus pattern.
 */
export function generateAngerVeinPath(cx: number, cy: number, size: number): string {
  const r = size * 0.4;
  const bulge = size * 0.25;
  // 4 curved lobes in + arrangement
  return [
    // Top lobe
    `M ${cx} ${cy - r * 0.2}`,
    `Q ${cx + bulge * 0.5} ${cy - r * 0.6}, ${cx} ${cy - r}`,
    `Q ${cx - bulge * 0.5} ${cy - r * 0.6}, ${cx} ${cy - r * 0.2}`,
    // Right lobe
    `M ${cx + r * 0.2} ${cy}`,
    `Q ${cx + r * 0.6} ${cy - bulge * 0.5}, ${cx + r} ${cy}`,
    `Q ${cx + r * 0.6} ${cy + bulge * 0.5}, ${cx + r * 0.2} ${cy}`,
    // Bottom lobe
    `M ${cx} ${cy + r * 0.2}`,
    `Q ${cx - bulge * 0.5} ${cy + r * 0.6}, ${cx} ${cy + r}`,
    `Q ${cx + bulge * 0.5} ${cy + r * 0.6}, ${cx} ${cy + r * 0.2}`,
    // Left lobe
    `M ${cx - r * 0.2} ${cy}`,
    `Q ${cx - r * 0.6} ${cy + bulge * 0.5}, ${cx - r} ${cy}`,
    `Q ${cx - r * 0.6} ${cy - bulge * 0.5}, ${cx - r * 0.2} ${cy}`,
  ].join(" ");
}

/**
 * Sprint 143b: Generate gloom lines ||| — parallel vertical wavy lines for despondent mood.
 */
export function generateGloomLinesPath(cx: number, cy: number, width: number, count: number = 3): string {
  const gap = width / (count + 1);
  const lineH = width * 0.8;
  const paths: string[] = [];
  for (let i = 1; i <= count; i++) {
    const lx = cx - width / 2 + gap * i;
    const top = cy - lineH / 2;
    const bot = cy + lineH / 2;
    const wave = width * 0.06;
    paths.push(
      `M ${lx} ${top}`,
      `C ${lx + wave} ${top + lineH * 0.33}, ${lx - wave} ${top + lineH * 0.66}, ${lx} ${bot}`,
    );
  }
  return paths.join(" ");
}

/**
 * Sprint 143b: Generate spiral path @_@ — dizzy/confused indicator.
 * Archimedean spiral with given number of turns.
 */
export function generateSpiralPath(cx: number, cy: number, radius: number, turns: number = 2.5): string {
  const points: string[] = [];
  const steps = Math.round(turns * 24);
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const angle = t * turns * Math.PI * 2;
    const r = t * radius;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    points.push(`${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`);
  }
  return points.join(" ");
}

/**
 * Sprint 143b: Generate flower path ✿ — 5-petal bloom for joy/satisfaction.
 */
export function generateFlowerPath(cx: number, cy: number, size: number, petals: number = 5): string {
  const outerR = size * 0.45;
  const innerR = size * 0.18;
  const points: string[] = [];
  for (let i = 0; i < petals * 2; i++) {
    const angle = (i * Math.PI) / petals - Math.PI / 2;
    const r = i % 2 === 0 ? outerR : innerR;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    points.push(`${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`);
  }
  points.push("Z");
  // Add center circle
  const centerR = size * 0.1;
  points.push(
    `M ${(cx + centerR).toFixed(2)} ${cy.toFixed(2)}`,
    `A ${centerR.toFixed(2)} ${centerR.toFixed(2)} 0 1 1 ${(cx - centerR).toFixed(2)} ${cy.toFixed(2)}`,
    `A ${centerR.toFixed(2)} ${centerR.toFixed(2)} 0 1 1 ${(cx + centerR).toFixed(2)} ${cy.toFixed(2)}`,
  );
  return points.join(" ");
}

/**
 * Sprint 143b: Generate Zzz path 💤 — stacked Z letters for sleepy indicator.
 * Three Z's of decreasing size, stacked vertically.
 */
export function generateZzzPath(cx: number, cy: number, size: number): string {
  const paths: string[] = [];
  const scales = [1.0, 0.7, 0.45];
  const offsets = [0, -size * 0.4, -size * 0.7];
  for (let i = 0; i < 3; i++) {
    const s = size * scales[i] * 0.4;
    const ox = cx + i * size * 0.12;
    const oy = cy + offsets[i];
    // Z shape: top-left → top-right → bottom-left → bottom-right
    paths.push(
      `M ${(ox - s).toFixed(2)} ${(oy - s * 0.5).toFixed(2)}`,
      `L ${(ox + s).toFixed(2)} ${(oy - s * 0.5).toFixed(2)}`,
      `L ${(ox - s).toFixed(2)} ${(oy + s * 0.5).toFixed(2)}`,
      `L ${(ox + s).toFixed(2)} ${(oy + s * 0.5).toFixed(2)}`,
    );
  }
  return paths.join(" ");
}

/**
 * Sprint 143b: Generate fire path 🔥 — flame shape for determination/passion.
 * Curved flame silhouette using bezier curves.
 */
export function generateFirePath(cx: number, cy: number, height: number): string {
  const w = height * 0.4;
  const top = cy - height * 0.6;
  const bot = cy + height * 0.4;
  return [
    `M ${cx} ${bot}`,
    // Left edge up
    `C ${cx - w * 0.8} ${cy}, ${cx - w * 1.2} ${cy - height * 0.3}, ${cx - w * 0.3} ${top + height * 0.15}`,
    // Tip
    `C ${cx - w * 0.1} ${top - height * 0.05}, ${cx + w * 0.1} ${top - height * 0.05}, ${cx + w * 0.3} ${top + height * 0.15}`,
    // Right edge down
    `C ${cx + w * 1.2} ${cy - height * 0.3}, ${cx + w * 0.8} ${cy}, ${cx} ${bot}`,
    "Z",
  ].join(" ");
}

// ─── Sprint 144: Mouth Interior Detail (Teeth + Tongue) ─────────────────

/**
 * Sprint 144: Generate a white arc at the top of an open mouth (upper teeth).
 * Only visible when mouth is open (openness > 0.15).
 */
export function generateTeethPath(
  cx: number,
  mouthY: number,
  baseWidth: number,
  widthMul: number,
  openness: number,
): string {
  const hw = (baseWidth / 2) * widthMul * 0.75; // teeth narrower than mouth
  const teethH = baseWidth * 0.08 * Math.min(openness * 2, 1); // shallow arc
  const curveY = mouthY - teethH * 0.2; // positioned just inside upper lip
  return [
    `M ${(cx - hw).toFixed(2)} ${curveY.toFixed(2)}`,
    `Q ${cx.toFixed(2)} ${(curveY + teethH).toFixed(2)}, ${(cx + hw).toFixed(2)} ${curveY.toFixed(2)}`,
    `L ${(cx + hw).toFixed(2)} ${(curveY + teethH * 0.5).toFixed(2)}`,
    `Q ${cx.toFixed(2)} ${(curveY + teethH * 1.3).toFixed(2)}, ${(cx - hw).toFixed(2)} ${(curveY + teethH * 0.5).toFixed(2)}`,
    "Z",
  ].join(" ");
}

/**
 * Sprint 144: Generate a pink bump at the bottom of the mouth interior (tongue hint).
 * Only visible when mouth is open enough.
 */
export function generateTonguePath(
  cx: number,
  mouthY: number,
  baseWidth: number,
  openness: number,
): string {
  const tongueW = baseWidth * 0.3;
  const openY = openness * baseWidth * 0.35;
  const tongueY = mouthY + openY * 0.6; // in lower half of mouth
  const tongueH = baseWidth * 0.06 * Math.min(openness * 2, 1);
  return [
    `M ${(cx - tongueW).toFixed(2)} ${tongueY.toFixed(2)}`,
    `Q ${cx.toFixed(2)} ${(tongueY + tongueH).toFixed(2)}, ${(cx + tongueW).toFixed(2)} ${tongueY.toFixed(2)}`,
    "Z",
  ].join(" ");
}

/**
 * Sprint 130: Generate an SVG path for a happy eye arc (^_^ shape).
 * Produces a downward-curving arc used for the "complete" state.
 *
 * @param cx - Eye center X
 * @param cy - Eye center Y
 * @param rx - Eye horizontal radius
 * @param ry - Eye vertical radius
 * @returns SVG path `d` string — upward arc like ^
 */
export function generateHappyEyePath(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
): string {
  // Quadratic bezier forming a ^ arc (smile-shaped curve for eye)
  const left = cx - rx;
  const right = cx + rx;
  const cpY = cy - ry * 0.9; // Control point above to make ^ shape
  return `M ${left.toFixed(1)} ${cy.toFixed(1)} Q ${cx.toFixed(1)} ${cpY.toFixed(1)}, ${right.toFixed(1)} ${cy.toFixed(1)}`;
}
