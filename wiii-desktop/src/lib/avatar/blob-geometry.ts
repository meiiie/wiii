/**
 * Noise-deformed circle to SVG path — Sprint 115: Living Avatar Foundation.
 * Uses Catmull-Rom to cubic Bezier conversion for smooth organic curves.
 */
import { sampleBlobNoise } from "./noise-engine";

/**
 * Generate an SVG path `d` string for a noise-deformed circle (organic blob).
 *
 * Each of `resolution` vertices around the circle is displaced radially by
 * 3D simplex noise, then connected with smooth Catmull-Rom curves.
 */
export function generateBlobPath(
  cx: number,
  cy: number,
  radius: number,
  resolution: number,
  time: number,
  frequency: number,
  amplitude: number,
  seed: number,
): string {
  if (resolution < 3) return "";

  const points: [number, number][] = [];
  for (let i = 0; i < resolution; i++) {
    const angle = (i / resolution) * Math.PI * 2;
    const deviation = sampleBlobNoise(angle, time, frequency, amplitude, seed);
    const r = radius * deviation;
    points.push([
      cx + Math.cos(angle) * r,
      cy + Math.sin(angle) * r,
    ]);
  }

  return pointsToSmoothPath(points);
}

/**
 * Convert closed polygon points to a smooth SVG path.
 * Catmull-Rom to cubic Bezier conversion, tension = 0.3.
 */
function pointsToSmoothPath(points: [number, number][]): string {
  const n = points.length;
  if (n < 3) return "";

  const tension = 0.3;
  const parts: string[] = [
    `M ${points[0][0].toFixed(2)} ${points[0][1].toFixed(2)}`,
  ];

  for (let i = 0; i < n; i++) {
    const p0 = points[(i - 1 + n) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];

    // Catmull-Rom to cubic Bezier control points
    const cp1x = p1[0] + (p2[0] - p0[0]) * tension / 3;
    const cp1y = p1[1] + (p2[1] - p0[1]) * tension / 3;
    const cp2x = p2[0] - (p3[0] - p1[0]) * tension / 3;
    const cp2y = p2[1] - (p3[1] - p1[1]) * tension / 3;

    parts.push(
      `C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2[0].toFixed(2)} ${p2[1].toFixed(2)}`
    );
  }

  parts.push("Z");
  return parts.join(" ");
}
