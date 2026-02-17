/**
 * Face geometry generation — Sprint 129: SVG Face on Blob.
 * Generates SVG paths/positions for eyes, mouth, and eyebrows
 * relative to the blob center and radius.
 */

/** Computed dimensions for all face features, relative to blob */
export interface FaceDimensions {
  /** Distance from center to each eye center (horizontal) */
  eyeSpacing: number;
  /** Eye vertical position (negative = above center) */
  eyeY: number;
  /** Eye horizontal radius */
  eyeRx: number;
  /** Eye vertical radius (base — modified by eyeOpenness) */
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
}

/**
 * Compute face feature dimensions from blob radius.
 * All values are proportional to blobRadius for size-adaptive rendering.
 */
export function getFaceDimensions(blobRadius: number): FaceDimensions {
  const faceScale = blobRadius * 0.82;
  return {
    eyeSpacing: faceScale * 0.30,
    eyeY: -faceScale * 0.08,
    eyeRx: faceScale * 0.18,
    eyeRy: faceScale * 0.22,
    pupilR: faceScale * 0.10,
    pupilMaxOffset: faceScale * 0.07,
    browY: -faceScale * 0.34,
    browHalfWidth: faceScale * 0.16,
    browStroke: Math.max(1.5, faceScale * 0.055),
    mouthY: faceScale * 0.24,
    mouthBaseWidth: faceScale * 0.38,
    mouthStroke: Math.max(1.5, faceScale * 0.05),
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
