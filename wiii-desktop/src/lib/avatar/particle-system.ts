/**
 * Lightweight ambient particle engine — Sprint 115: Living Avatar Foundation.
 * Canvas 2D rendering for large tier avatars only.
 */
import type { Particle } from "./types";

/**
 * Spawn a new particle near center with initial orbital angle.
 */
export function spawnParticle(
  cx: number,
  cy: number,
  baseRadius: number,
): Particle {
  const angle = Math.random() * Math.PI * 2;
  const orbitRadius = baseRadius * (0.6 + Math.random() * 0.5);
  return {
    x: cx + Math.cos(angle) * orbitRadius * 0.3,
    y: cy + Math.sin(angle) * orbitRadius * 0.3,
    vx: 0,
    vy: 0,
    life: 1.0,
    maxLife: 2 + Math.random() * 3,
    size: 1 + Math.random() * 1.5,
    angle,
    orbitRadius,
  };
}

/**
 * Update all particles: orbital motion + damping + life decay.
 * Returns surviving particles (filters out dead ones).
 */
export function updateParticles(
  particles: Particle[],
  cx: number,
  cy: number,
  dt: number,
  orbitSpeed: number,
  driftSpeed: number,
): Particle[] {
  const result: Particle[] = [];

  for (const p of particles) {
    // Advance orbital angle
    p.angle += orbitSpeed * dt;

    // Target position on orbit
    const targetX = cx + Math.cos(p.angle) * p.orbitRadius;
    const targetY = cy + Math.sin(p.angle) * p.orbitRadius;

    // Pull toward orbit with spring-like force
    const pullStrength = 2.0;
    p.vx += (targetX - p.x) * pullStrength * dt;
    p.vy += (targetY - p.y) * pullStrength * dt;

    // Outward drift
    const dx = p.x - cx;
    const dy = p.y - cy;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    p.vx += (dx / dist) * driftSpeed * dt;
    p.vy += (dy / dist) * driftSpeed * dt;

    // Damping
    p.vx *= 0.95;
    p.vy *= 0.95;

    // Integrate position
    p.x += p.vx * dt;
    p.y += p.vy * dt;

    // Life decay
    p.life -= dt / p.maxLife;

    if (p.life > 0) {
      result.push(p);
    }
  }

  return result;
}

/**
 * Render particles to a Canvas 2D context.
 */
export function renderParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  color: string,
): void {
  for (const p of particles) {
    const alpha = Math.max(0, p.life) * 0.6;
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
