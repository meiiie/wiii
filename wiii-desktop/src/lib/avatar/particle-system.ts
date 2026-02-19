/**
 * Lightweight ambient particle engine — Sprint 115: Living Avatar Foundation.
 * Sprint 134: Life-based size pulsing, shaped particles, burst emitter.
 * Canvas 2D rendering for large tier avatars only.
 */
import type { Particle } from "./types";

// ─── Burst Particle System (Sprint 134) ────────────────────────────

/** Shape types for burst particles */
export type ParticleShape = "dot" | "heart" | "star" | "ring" | "teardrop";

/** One-shot burst particle with shape + color */
export interface BurstParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** 1→0, decays over time */
  life: number;
  size: number;
  /** Visual rotation (radians) */
  rotation: number;
  /** Rotation speed (rad/s) */
  rotSpeed: number;
  shape: ParticleShape;
  color: string;
}

/** Spawn a radial burst of shaped particles */
export function spawnBurst(
  cx: number,
  cy: number,
  count: number,
  shape: ParticleShape,
  color: string,
  speedRange: [number, number] = [40, 80],
  sizeRange: [number, number] = [2, 5],
): BurstParticle[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2 + (Math.random() - 0.5) * 0.6;
    const speed = speedRange[0] + Math.random() * (speedRange[1] - speedRange[0]);
    return {
      x: cx + (Math.random() - 0.5) * 4,
      y: cy + (Math.random() - 0.5) * 4,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1.0,
      size: sizeRange[0] + Math.random() * (sizeRange[1] - sizeRange[0]),
      rotation: Math.random() * Math.PI * 2,
      rotSpeed: (Math.random() - 0.5) * 4,
      shape,
      color,
    };
  });
}

/** Spawn downward-falling burst (for teardrops/rain) */
export function spawnFallingBurst(
  cx: number,
  cy: number,
  count: number,
  shape: ParticleShape,
  color: string,
): BurstParticle[] {
  return Array.from({ length: count }, () => ({
    x: cx + (Math.random() - 0.5) * 20,
    y: cy - Math.random() * 10,
    vx: (Math.random() - 0.5) * 15,
    vy: 20 + Math.random() * 30,
    life: 1.0,
    size: 2 + Math.random() * 2,
    rotation: 0,
    rotSpeed: 0,
    shape,
    color,
  }));
}

/** Update burst particles — linear motion with gravity + friction */
export function updateBurstParticles(
  particles: BurstParticle[],
  dt: number,
): BurstParticle[] {
  const result: BurstParticle[] = [];
  for (const p of particles) {
    p.vx *= 0.97;
    p.vy *= 0.97;
    p.vy += 20 * dt; // light gravity
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.rotation += p.rotSpeed * dt;
    p.life -= dt * 0.8; // ~1.25s lifespan
    if (p.life > 0) result.push(p);
  }
  return result;
}

// ─── Shape Drawing Functions ───────────────────────────────────────

function drawHeart(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, rot: number): void {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.beginPath();
  ctx.moveTo(0, r * 0.3);
  ctx.bezierCurveTo(-r, -r * 0.3, -r * 0.5, -r * 1.2, 0, -r * 0.5);
  ctx.bezierCurveTo(r * 0.5, -r * 1.2, r, -r * 0.3, 0, r * 0.3);
  ctx.fill();
  ctx.restore();
}

function drawStar4(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, rot: number): void {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.beginPath();
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 - Math.PI / 2;
    const inner = (i / 4 + 0.125) * Math.PI * 2 - Math.PI / 2;
    ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
    ctx.lineTo(Math.cos(inner) * r * 0.4, Math.sin(inner) * r * 0.4);
  }
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawRing(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.arc(x, y, r * 0.55, 0, Math.PI * 2, true);
  ctx.fill();
}

function drawTeardrop(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.save();
  ctx.translate(x, y);
  ctx.beginPath();
  ctx.moveTo(0, -r * 1.2);
  ctx.bezierCurveTo(r * 0.6, -r * 0.3, r * 0.5, r * 0.5, 0, r * 0.5);
  ctx.bezierCurveTo(-r * 0.5, r * 0.5, -r * 0.6, -r * 0.3, 0, -r * 1.2);
  ctx.fill();
  ctx.restore();
}

/** Render burst particles with shape dispatch */
export function renderBurstParticles(
  ctx: CanvasRenderingContext2D,
  particles: BurstParticle[],
): void {
  for (const p of particles) {
    const alpha = Math.max(0, p.life) * 0.8;
    const drawSize = p.size * (0.3 + 0.7 * Math.sqrt(Math.max(0, p.life)));
    ctx.globalAlpha = alpha;
    ctx.fillStyle = p.color;

    switch (p.shape) {
      case "heart":
        drawHeart(ctx, p.x, p.y, drawSize, p.rotation);
        break;
      case "star":
        drawStar4(ctx, p.x, p.y, drawSize, p.rotation);
        break;
      case "ring":
        drawRing(ctx, p.x, p.y, drawSize);
        break;
      case "teardrop":
        drawTeardrop(ctx, p.x, p.y, drawSize);
        break;
      default: // dot
        ctx.beginPath();
        ctx.arc(p.x, p.y, drawSize, 0, Math.PI * 2);
        ctx.fill();
        break;
    }
  }
  ctx.globalAlpha = 1;
}

// ─── Original Orbital Particle System ──────────────────────────────

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
    // Sprint 134: Life-based size — particles shrink as they fade
    const drawSize = p.size * (0.4 + 0.6 * Math.sqrt(Math.max(0, p.life)));
    ctx.beginPath();
    ctx.arc(p.x, p.y, drawSize, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
