/**
 * Simplex noise singleton — Sprint 115: Living Avatar Foundation.
 * Shared 3D noise generator across all avatar instances.
 */
import { createNoise3D } from "simplex-noise";

/** Shared 3D noise function — lazily initialized singleton */
let _noise3D: ((x: number, y: number, z: number) => number) | null = null;

export function getNoiseGenerator(): (x: number, y: number, z: number) => number {
  if (!_noise3D) {
    _noise3D = createNoise3D();
  }
  return _noise3D;
}

/**
 * Sample blob noise at a given angle around the perimeter.
 * Returns a deviation factor near 1.0 +/- amplitude.
 *
 * @param angle - Position around circle (0 to 2*PI)
 * @param time - Animation time driver
 * @param frequency - Spatial detail level
 * @param amplitude - Deformation intensity (0-1)
 * @param seed - Per-instance offset to prevent lockstep
 */
export function sampleBlobNoise(
  angle: number,
  time: number,
  frequency: number,
  amplitude: number,
  seed: number,
): number {
  const noise3D = getNoiseGenerator();
  const nx = Math.cos(angle) * frequency;
  const ny = Math.sin(angle) * frequency;
  const nz = time + seed;
  return 1.0 + noise3D(nx, ny, nz) * amplitude;
}
