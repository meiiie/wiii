/**
 * WiiiAvatar — living organic blob avatar for Wiii's visual identity.
 * Sprint 115: Living Avatar System Foundation.
 * Sprint 119: Aria labels (a11y), reduced-motion-aware rendering.
 * Sprint 130: Clipping fix, eye shine, blush, happy eyes, viewBox padding.
 * Sprint 131: Kawaii Phase 1 — anime eyes (iris gradient, clipPath), nose, blush hash.
 *
 * 3-tier rendering:
 *   Tiny  (<=20px) — CSS-only motion.div (backward compat with Sprint 111)
 *   Medium (22-36px) — SVG noise-deformed blob + glow filter
 *   Large  (>=40px) — Canvas particles + SVG blob + glow + indicator + face
 */
import { memo, useRef, useEffect } from "react";
import { motion } from "motion/react";
import type { AvatarState, WiiiAvatarProps } from "./types";
import { getSizeTier, STATE_CONFIG } from "./state-config";
import { useAvatarAnimation } from "./use-avatar-animation";
import { getFaceDimensions, generateMouthPath, generateHappyEyePath, generateStarPupilPath, generateHeartPupilPath, generateAngerVeinPath, generateGloomLinesPath, generateSpiralPath, generateFlowerPath, generateZzzPath, generateFirePath } from "./face-geometry";
import { FACE_EXPRESSIONS } from "./face-config";
import {
  generateSparklePath,
  generateSweatDropPath,
  generateMusicNotePath,
  generateHeartPath,
  generateExclaimPath,
  generateQuestionPath,
  SPARKLE_POSITIONS,
  THOUGHT_POSITION,
  SWEAT_POSITION,
  MUSIC_POSITION,
  HEART_POSITIONS,
  EXCLAIM_POSITION,
  QUESTION_POSITION,
  ANGER_VEIN_POSITION,
  GLOOM_POSITION,
  SPIRAL_POSITION,
  FLOWER_POSITIONS,
  ZZZ_POSITION,
  FIRE_POSITION,
} from "./manga-indicators";
import "./avatar.css";

export type { AvatarState } from "./types";

/** Aria labels for screen readers — Vietnamese state descriptions */
export const STATE_LABELS: Record<AvatarState, string> = {
  idle: "Wiii",
  listening: "Wiii — đang lắng nghe",
  thinking: "Wiii — đang suy nghĩ",
  speaking: "Wiii — đang trả lời",
  complete: "Wiii — đã hoàn thành",
  error: "Wiii — gặp lỗi",
};

/** Sprint 130: Padding ratio for viewBox expansion (15%) */
const VIEWBOX_PAD_RATIO = 0.15;

/** Sprint 131: Blush hash line angle (degrees from horizontal — nearly vertical) */
const BLUSH_HASH_ANGLE_DEG = 70;
const BLUSH_HASH_ANGLE_RAD = (BLUSH_HASH_ANGLE_DEG * Math.PI) / 180;

/** Sprint 131: Generate 3 hash line coordinates for one cheek */
function getBlushHashLines(
  cx: number,
  cy: number,
  len: number,
  gap: number,
): Array<{ x1: number; y1: number; x2: number; y2: number }> {
  const dx = Math.cos(BLUSH_HASH_ANGLE_RAD) * len * 0.5;
  const dy = Math.sin(BLUSH_HASH_ANGLE_RAD) * len * 0.5;
  return [-1, 0, 1].map((i) => ({
    x1: cx + i * gap - dx,
    y1: cy + dy,
    x2: cx + i * gap + dx,
    y2: cy - dy,
  }));
}

/** Sprint 129+130+131+143+144: Face SVG group — kawaii anime eyes, nose, blush, happy eyes, star/heart pupils, teeth, tongue, tears, hair */
function FaceGroup({
  halfSize,
  blobRadius,
  instanceId,
  faceGroupRef,
  leftEyeRef,
  rightEyeRef,
  leftIrisRef,
  rightIrisRef,
  leftBrowRef,
  rightBrowRef,
  mouthRef,
  leftBlushRef,
  rightBlushRef,
  leftHappyRef,
  rightHappyRef,
  leftStarRef,
  rightStarRef,
  leftHeartRef,
  rightHeartRef,
  leftKORef,
  rightKORef,
  teethRef,
  tongueRef,
  mouthGlintRef,
  leftTearRef,
  rightTearRef,
  leftMoistureRef,
  rightMoistureRef,
  state,
}: {
  halfSize: number;
  blobRadius: number;
  instanceId: number;
  faceGroupRef: React.RefObject<SVGGElement | null>;
  leftEyeRef: React.RefObject<SVGGElement | null>;
  rightEyeRef: React.RefObject<SVGGElement | null>;
  leftIrisRef: React.RefObject<SVGGElement | null>;
  rightIrisRef: React.RefObject<SVGGElement | null>;
  leftBrowRef: React.RefObject<SVGLineElement | null>;
  rightBrowRef: React.RefObject<SVGLineElement | null>;
  mouthRef: React.RefObject<SVGPathElement | null>;
  leftBlushRef: React.RefObject<SVGEllipseElement | null>;
  rightBlushRef: React.RefObject<SVGEllipseElement | null>;
  leftHappyRef: React.RefObject<SVGPathElement | null>;
  rightHappyRef: React.RefObject<SVGPathElement | null>;
  leftStarRef: React.RefObject<SVGPathElement | null>;
  rightStarRef: React.RefObject<SVGPathElement | null>;
  leftHeartRef: React.RefObject<SVGPathElement | null>;
  rightHeartRef: React.RefObject<SVGPathElement | null>;
  leftKORef: React.RefObject<SVGPathElement | null>;
  rightKORef: React.RefObject<SVGPathElement | null>;
  teethRef: React.RefObject<SVGPathElement | null>;
  tongueRef: React.RefObject<SVGPathElement | null>;
  mouthGlintRef: React.RefObject<SVGCircleElement | null>;
  leftTearRef: React.RefObject<SVGPathElement | null>;
  rightTearRef: React.RefObject<SVGPathElement | null>;
  leftMoistureRef: React.RefObject<SVGCircleElement | null>;
  rightMoistureRef: React.RefObject<SVGCircleElement | null>;
  state: AvatarState;
}) {
  const dims = getFaceDimensions(blobRadius);
  const faceExpr = FACE_EXPRESSIONS[state] || FACE_EXPRESSIONS.idle;

  // Initial mouth path (updated at 60fps via rAF in the hook)
  const initialMouth = generateMouthPath(0, dims.mouthY, {
    curve: faceExpr.mouthCurve,
    openness: faceExpr.mouthOpenness,
    width: faceExpr.mouthWidth,
  }, dims.mouthBaseWidth);

  // Happy eye paths
  const leftHappyPath = generateHappyEyePath(-dims.eyeSpacing, dims.eyeY, dims.eyeRx, dims.eyeRy);
  const rightHappyPath = generateHappyEyePath(dims.eyeSpacing, dims.eyeY, dims.eyeRx, dims.eyeRy);

  // Sprint 131: Unique IDs for gradients + clipPaths (per-instance)
  const irisGradId = `wiii-iris-${instanceId}`;
  const clipIdL = `wiii-eye-clip-l-${instanceId}`;
  const clipIdR = `wiii-eye-clip-r-${instanceId}`;

  // Sprint 131: Blush hash lines (3 per cheek)
  const leftHash = getBlushHashLines(-dims.blushX, dims.blushY, dims.blushHashLen, dims.blushHashGap);
  const rightHash = getBlushHashLines(dims.blushX, dims.blushY, dims.blushHashLen, dims.blushHashGap);

  return (
    <g
      ref={faceGroupRef as React.Ref<SVGGElement>}
      className="wiii-face"
      transform={`translate(${halfSize}, ${halfSize})`}
      style={{ pointerEvents: "none" }}
    >
      {/* Sprint 131: Defs — iris gradient + eye clipPaths */}
      <defs>
        <radialGradient id={irisGradId} cx="45%" cy="40%" r="55%">
          <stop offset="0%" stopColor="#fbbf24" />
          <stop offset="45%" stopColor="#d97706" />
          <stop offset="100%" stopColor="#92400e" />
        </radialGradient>
        <clipPath id={clipIdL}>
          <ellipse cx={-dims.eyeSpacing} cy={dims.eyeY} rx={dims.eyeRx} ry={dims.eyeRy} />
        </clipPath>
        <clipPath id={clipIdR}>
          <ellipse cx={dims.eyeSpacing} cy={dims.eyeY} rx={dims.eyeRx} ry={dims.eyeRy} />
        </clipPath>
      </defs>

      {/* Left eye — sclera (fixed) + clipped iris group (gaze tracking) */}
      <g ref={leftEyeRef as React.Ref<SVGGElement>} className="wiii-face-eye" style={{ willChange: "transform" }}>
        <ellipse
          cx={-dims.eyeSpacing}
          cy={dims.eyeY}
          rx={dims.eyeRx}
          ry={dims.eyeRy}
          fill="white"
        />
        <g ref={leftIrisRef as React.Ref<SVGGElement>} className="wiii-face-iris" clipPath={`url(#${clipIdL})`}>
          <ellipse
            cx={-dims.eyeSpacing}
            cy={dims.eyeY}
            rx={dims.irisRx}
            ry={dims.irisRy}
            fill={`url(#${irisGradId})`}
          />
          <circle
            cx={-dims.eyeSpacing}
            cy={dims.eyeY}
            r={dims.pupilR}
            fill="#1a1a1a"
            className="wiii-face-pupil"
          />
          <circle
            cx={-dims.eyeSpacing + dims.shineOffsetX1}
            cy={dims.eyeY + dims.shineOffsetY1}
            r={dims.shineR1}
            fill="white"
            opacity={0.9}
            className="wiii-face-shine"
          />
          <circle
            cx={-dims.eyeSpacing + dims.shineOffsetX2}
            cy={dims.eyeY + dims.shineOffsetY2}
            r={dims.shineR2}
            fill="white"
            opacity={0.6}
            className="wiii-face-shine"
          />
          {/* Sprint 143: Star pupil overlay ★ */}
          <path
            ref={leftStarRef as React.Ref<SVGPathElement>}
            d={generateStarPupilPath(-dims.eyeSpacing, dims.eyeY, dims.pupilR * 1.3)}
            fill="#fbbf24"
            opacity={0}
            className="wiii-face-star-pupil"
          />
          {/* Sprint 143: Heart pupil overlay ♥ */}
          <path
            ref={leftHeartRef as React.Ref<SVGPathElement>}
            d={generateHeartPupilPath(-dims.eyeSpacing, dims.eyeY, dims.pupilR * 1.2)}
            fill="#ff6b9d"
            opacity={0}
            className="wiii-face-heart-pupil"
          />
          {/* Sprint 144: Knocked-out eye × overlay */}
          <path
            ref={leftKORef as React.Ref<SVGPathElement>}
            d=""
            fill="none"
            stroke="white"
            strokeWidth={dims.browStroke * 1.5}
            strokeLinecap="round"
            opacity={0}
            className="wiii-face-ko-eye"
          />
        </g>
      </g>

      {/* Right eye — sclera (fixed) + clipped iris group (gaze tracking) */}
      <g ref={rightEyeRef as React.Ref<SVGGElement>} className="wiii-face-eye" style={{ willChange: "transform" }}>
        <ellipse
          cx={dims.eyeSpacing}
          cy={dims.eyeY}
          rx={dims.eyeRx}
          ry={dims.eyeRy}
          fill="white"
        />
        <g ref={rightIrisRef as React.Ref<SVGGElement>} className="wiii-face-iris" clipPath={`url(#${clipIdR})`}>
          <ellipse
            cx={dims.eyeSpacing}
            cy={dims.eyeY}
            rx={dims.irisRx}
            ry={dims.irisRy}
            fill={`url(#${irisGradId})`}
          />
          <circle
            cx={dims.eyeSpacing}
            cy={dims.eyeY}
            r={dims.pupilR}
            fill="#1a1a1a"
            className="wiii-face-pupil"
          />
          <circle
            cx={dims.eyeSpacing + dims.shineOffsetX1}
            cy={dims.eyeY + dims.shineOffsetY1}
            r={dims.shineR1}
            fill="white"
            opacity={0.9}
            className="wiii-face-shine"
          />
          <circle
            cx={dims.eyeSpacing + dims.shineOffsetX2}
            cy={dims.eyeY + dims.shineOffsetY2}
            r={dims.shineR2}
            fill="white"
            opacity={0.6}
            className="wiii-face-shine"
          />
          {/* Sprint 143: Star pupil overlay ★ */}
          <path
            ref={rightStarRef as React.Ref<SVGPathElement>}
            d={generateStarPupilPath(dims.eyeSpacing, dims.eyeY, dims.pupilR * 1.3)}
            fill="#fbbf24"
            opacity={0}
            className="wiii-face-star-pupil"
          />
          {/* Sprint 143: Heart pupil overlay ♥ */}
          <path
            ref={rightHeartRef as React.Ref<SVGPathElement>}
            d={generateHeartPupilPath(dims.eyeSpacing, dims.eyeY, dims.pupilR * 1.2)}
            fill="#ff6b9d"
            opacity={0}
            className="wiii-face-heart-pupil"
          />
          {/* Sprint 144: Knocked-out eye × overlay */}
          <path
            ref={rightKORef as React.Ref<SVGPathElement>}
            d=""
            fill="none"
            stroke="white"
            strokeWidth={dims.browStroke * 1.5}
            strokeLinecap="round"
            opacity={0}
            className="wiii-face-ko-eye"
          />
        </g>
      </g>

      {/* Happy eye arcs ^_^ — outside eye groups (don't blink) */}
      <path
        ref={leftHappyRef as React.Ref<SVGPathElement>}
        className="wiii-face-happy"
        d={leftHappyPath}
        fill="none"
        stroke="white"
        strokeWidth={dims.browStroke * 1.2}
        strokeLinecap="round"
        opacity={0}
      />
      <path
        ref={rightHappyRef as React.Ref<SVGPathElement>}
        className="wiii-face-happy"
        d={rightHappyPath}
        fill="none"
        stroke="white"
        strokeWidth={dims.browStroke * 1.2}
        strokeLinecap="round"
        opacity={0}
      />

      {/* Left eyebrow */}
      <line
        ref={leftBrowRef as React.Ref<SVGLineElement>}
        className="wiii-face-brow"
        x1={-dims.eyeSpacing - dims.browHalfWidth}
        y1={dims.browY}
        x2={-dims.eyeSpacing + dims.browHalfWidth}
        y2={dims.browY}
        stroke="white"
        strokeWidth={dims.browStroke}
        strokeLinecap="round"
        style={{ willChange: "transform" }}
      />

      {/* Right eyebrow */}
      <line
        ref={rightBrowRef as React.Ref<SVGLineElement>}
        className="wiii-face-brow"
        x1={dims.eyeSpacing - dims.browHalfWidth}
        y1={dims.browY}
        x2={dims.eyeSpacing + dims.browHalfWidth}
        y2={dims.browY}
        stroke="white"
        strokeWidth={dims.browStroke}
        strokeLinecap="round"
        style={{ willChange: "transform" }}
      />

      {/* Sprint 131: Nose — minimal dot */}
      <circle
        className="wiii-face-nose"
        cx={0}
        cy={dims.noseY}
        r={dims.noseR}
        fill="rgba(255,255,255,0.35)"
      />

      {/* Blush ellipses — below eyes */}
      <ellipse
        ref={leftBlushRef as React.Ref<SVGEllipseElement>}
        className="wiii-face-blush"
        cx={-dims.blushX}
        cy={dims.blushY}
        rx={dims.blushRx}
        ry={dims.blushRy}
        fill="#ff6b9d"
        opacity={0}
      />
      <ellipse
        ref={rightBlushRef as React.Ref<SVGEllipseElement>}
        className="wiii-face-blush"
        cx={dims.blushX}
        cy={dims.blushY}
        rx={dims.blushRx}
        ry={dims.blushRy}
        fill="#ff6b9d"
        opacity={0}
      />

      {/* Sprint 131: Blush hash lines /// — anime diagonal strokes */}
      {leftHash.map((l, i) => (
        <line
          key={`lh${i}`}
          className="wiii-face-blush-hash"
          x1={l.x1}
          y1={l.y1}
          x2={l.x2}
          y2={l.y2}
          stroke="#ff6b9d"
          strokeWidth={dims.blushHashStroke}
          strokeLinecap="round"
          opacity={0}
        />
      ))}
      {rightHash.map((l, i) => (
        <line
          key={`rh${i}`}
          className="wiii-face-blush-hash"
          x1={l.x1}
          y1={l.y1}
          x2={l.x2}
          y2={l.y2}
          stroke="#ff6b9d"
          strokeWidth={dims.blushHashStroke}
          strokeLinecap="round"
          opacity={0}
        />
      ))}

      {/* Mouth */}
      <path
        ref={mouthRef as React.Ref<SVGPathElement>}
        className="wiii-face-mouth"
        d={initialMouth}
        fill={faceExpr.mouthOpenness >= 0.05 ? "rgba(0,0,0,0.3)" : "none"}
        stroke="white"
        strokeWidth={dims.mouthStroke}
        strokeLinecap="round"
      />

      {/* Sprint 144: Mouth interior — teeth, tongue, glint */}
      <path ref={teethRef as React.Ref<SVGPathElement>} className="wiii-face-teeth" fill="rgba(255,255,255,0.85)" stroke="none" opacity={0} />
      <path ref={tongueRef as React.Ref<SVGPathElement>} className="wiii-face-tongue" fill="#ff8fab" stroke="none" opacity={0} />
      <circle ref={mouthGlintRef as React.Ref<SVGCircleElement>} className="wiii-face-mouth-glint" r={dims.mouthBaseWidth * 0.04} fill="white" opacity={0} />

      {/* Sprint 144: Eye moisture shine — lower-eye glint for glassy effect */}
      <circle
        ref={leftMoistureRef as React.Ref<SVGCircleElement>}
        className="wiii-face-moisture-shine"
        cx={-dims.eyeSpacing}
        cy={dims.eyeY + dims.eyeRy * 0.6}
        r={dims.eyeRx * 0.5}
        fill="rgba(180,220,255,0.3)"
        opacity={0}
      />
      <circle
        ref={rightMoistureRef as React.Ref<SVGCircleElement>}
        className="wiii-face-moisture-shine"
        cx={dims.eyeSpacing}
        cy={dims.eyeY + dims.eyeRy * 0.6}
        r={dims.eyeRx * 0.5}
        fill="rgba(180,220,255,0.3)"
        opacity={0}
      />

      {/* Sprint 144: Tear drops */}
      <path ref={leftTearRef as React.Ref<SVGPathElement>} className="wiii-face-tear" fill="#93c5fd" opacity={0} />
      <path ref={rightTearRef as React.Ref<SVGPathElement>} className="wiii-face-tear" fill="#93c5fd" opacity={0} />

    </g>
  );
}

/** Sprint 131 Phase 4 + Sprint 143/143b: Manga indicator SVG elements around the blob */
function MangaIndicatorGroup({
  halfSize,
  blobRadius,
  sparkleRef,
  thoughtRef,
  sweatRef,
  musicRef,
  heartRef,
  exclaimRef,
  questionRef,
  angerVeinRef,
  gloomRef,
  spiralRef,
  flowerRef,
  zzzRef,
  fireRef,
  state: _state,
}: {
  halfSize: number;
  blobRadius: number;
  sparkleRef: React.RefObject<SVGGElement | null>;
  thoughtRef: React.RefObject<SVGGElement | null>;
  sweatRef: React.RefObject<SVGGElement | null>;
  musicRef: React.RefObject<SVGGElement | null>;
  heartRef: React.RefObject<SVGGElement | null>;
  exclaimRef: React.RefObject<SVGGElement | null>;
  questionRef: React.RefObject<SVGGElement | null>;
  angerVeinRef: React.RefObject<SVGGElement | null>;
  gloomRef: React.RefObject<SVGGElement | null>;
  spiralRef: React.RefObject<SVGGElement | null>;
  flowerRef: React.RefObject<SVGGElement | null>;
  zzzRef: React.RefObject<SVGGElement | null>;
  fireRef: React.RefObject<SVGGElement | null>;
  state: AvatarState;
}) {
  const br = blobRadius;
  const starSize = br * 0.12;

  return (
    <g
      className="wiii-manga-indicators"
      transform={`translate(${halfSize}, ${halfSize})`}
      style={{ pointerEvents: "none" }}
    >
      {/* Sparkles ✨ — 3 stars (complete state) */}
      <g ref={sparkleRef as React.Ref<SVGGElement>} className="wiii-indicator-sparkle" opacity={0}>
        {SPARKLE_POSITIONS.map((pos, i) => (
          <path
            key={`sp${i}`}
            d={generateSparklePath(pos.x * br, pos.y * br, starSize * (1 - i * 0.15))}
            fill="#fbbf24"
            opacity={0.9}
          />
        ))}
      </g>

      {/* Thought bubble 💭 (thinking state) */}
      <g ref={thoughtRef as React.Ref<SVGGElement>} className="wiii-indicator-thought" opacity={0}>
        {/* Cloud body */}
        <ellipse
          cx={THOUGHT_POSITION.x * br}
          cy={THOUGHT_POSITION.y * br}
          rx={br * 0.20}
          ry={br * 0.14}
          fill="white"
          opacity={0.9}
          stroke="rgba(0,0,0,0.15)"
          strokeWidth={1}
        />
        {/* Trail dots (small → smaller) */}
        <circle cx={THOUGHT_POSITION.x * br * 0.7} cy={THOUGHT_POSITION.y * br * 0.65} r={br * 0.04} fill="white" opacity={0.8} />
        <circle cx={THOUGHT_POSITION.x * br * 0.55} cy={THOUGHT_POSITION.y * br * 0.4} r={br * 0.025} fill="white" opacity={0.7} />
        {/* Animated dots inside cloud (...) */}
        <circle className="wiii-thought-dot" cx={THOUGHT_POSITION.x * br - br * 0.08} cy={THOUGHT_POSITION.y * br} r={br * 0.025} fill="#666" />
        <circle className="wiii-thought-dot" cx={THOUGHT_POSITION.x * br} cy={THOUGHT_POSITION.y * br} r={br * 0.025} fill="#666" />
        <circle className="wiii-thought-dot" cx={THOUGHT_POSITION.x * br + br * 0.08} cy={THOUGHT_POSITION.y * br} r={br * 0.025} fill="#666" />
      </g>

      {/* Sweat drop 💧 (error state) */}
      <g ref={sweatRef as React.Ref<SVGGElement>} className="wiii-indicator-sweat" opacity={0}>
        <path
          d={generateSweatDropPath(SWEAT_POSITION.x * br, SWEAT_POSITION.y * br, br * 0.10, br * 0.18)}
          fill="#93c5fd"
          opacity={0.85}
        />
      </g>

      {/* Music note ♪ (idle state) */}
      <g ref={musicRef as React.Ref<SVGGElement>} className="wiii-indicator-music" opacity={0}>
        <path
          d={generateMusicNotePath(MUSIC_POSITION.x * br, MUSIC_POSITION.y * br, br * 0.18)}
          fill="white"
          opacity={0.7}
          stroke="none"
        />
      </g>

      {/* Sprint 143: Hearts ♥ — 2 floating hearts (excited/warm mood) */}
      <g ref={heartRef as React.Ref<SVGGElement>} className="wiii-indicator-heart" opacity={0}>
        {HEART_POSITIONS.map((pos, i) => (
          <path
            key={`ht${i}`}
            d={generateHeartPath(pos.x * br, pos.y * br, br * (0.14 - i * 0.02))}
            fill="#ff6b9d"
            opacity={0.85}
          />
        ))}
      </g>

      {/* Sprint 143: Exclamation mark ❗ (listening state) */}
      <g ref={exclaimRef as React.Ref<SVGGElement>} className="wiii-indicator-exclaim" opacity={0}>
        <path
          d={generateExclaimPath(EXCLAIM_POSITION.x * br, EXCLAIM_POSITION.y * br, br * 0.22)}
          fill="#fbbf24"
          opacity={0.9}
        />
      </g>

      {/* Sprint 143: Question mark ❓ (thinking+concerned) */}
      <g ref={questionRef as React.Ref<SVGGElement>} className="wiii-indicator-question" opacity={0}>
        <path
          d={generateQuestionPath(QUESTION_POSITION.x * br, QUESTION_POSITION.y * br, br * 0.24)}
          fill="white"
          opacity={0.85}
          stroke="rgba(0,0,0,0.15)"
          strokeWidth={0.5}
        />
      </g>

      {/* Sprint 143b: Anger vein 💢 (soul-triggered frustration) */}
      <g ref={angerVeinRef as React.Ref<SVGGElement>} className="wiii-manga-anger-vein" opacity={0}>
        <path
          d={generateAngerVeinPath(ANGER_VEIN_POSITION.x * br, ANGER_VEIN_POSITION.y * br, br * 0.16)}
          fill="#ef4444"
          opacity={0.85}
        />
      </g>

      {/* Sprint 143b: Gloom lines ||| (despondent mood) */}
      <g ref={gloomRef as React.Ref<SVGGElement>} className="wiii-manga-gloom" opacity={0}>
        <path
          d={generateGloomLinesPath(GLOOM_POSITION.x * br, GLOOM_POSITION.y * br, br * 0.3)}
          fill="none"
          stroke="#6b7280"
          strokeWidth={1.5}
          strokeLinecap="round"
          opacity={0.7}
        />
      </g>

      {/* Sprint 143b: Spiral @_@ (dizzy/confused) */}
      <g ref={spiralRef as React.Ref<SVGGElement>} className="wiii-manga-spiral" opacity={0}>
        <path
          d={generateSpiralPath(SPIRAL_POSITION.x * br, SPIRAL_POSITION.y * br, br * 0.12)}
          fill="none"
          stroke="#a78bfa"
          strokeWidth={1.5}
          strokeLinecap="round"
          opacity={0.8}
        />
      </g>

      {/* Sprint 143b: Flower bloom ✿ (joyful completion) */}
      <g ref={flowerRef as React.Ref<SVGGElement>} className="wiii-manga-flower" opacity={0}>
        {FLOWER_POSITIONS.map((pos, i) => (
          <path
            key={`fl${i}`}
            d={generateFlowerPath(pos.x * br, pos.y * br, br * (0.12 - i * 0.015))}
            fill="#f9a8d4"
            opacity={0.8}
          />
        ))}
      </g>

      {/* Sprint 143b: Zzz 💤 (sleepy gentle idle) */}
      <g ref={zzzRef as React.Ref<SVGGElement>} className="wiii-manga-zzz" opacity={0}>
        <path
          d={generateZzzPath(ZZZ_POSITION.x * br, ZZZ_POSITION.y * br, br * 0.18)}
          fill="none"
          stroke="#94a3b8"
          strokeWidth={1.5}
          strokeLinecap="round"
          opacity={0.7}
        />
      </g>

      {/* Sprint 143b: Fire spirit 🔥 (determination/passion) */}
      <g ref={fireRef as React.Ref<SVGGElement>} className="wiii-manga-fire" opacity={0}>
        <path
          d={generateFirePath(FIRE_POSITION.x * br, FIRE_POSITION.y * br, br * 0.22)}
          fill="#f97316"
          opacity={0.85}
        />
      </g>
    </g>
  );
}

/** Global instance counter for unique SVG filter IDs */
let _instanceCounter = 0;

function WiiiAvatarInner({ state = "idle", size = 24, className = "", mood = "neutral", soulEmotion = null }: WiiiAvatarProps) {
  const tier = getSizeTier(size);
  const fontSize = Math.round(size * 0.42);
  const config = STATE_CONFIG[state] || STATE_CONFIG.idle;

  // Unique filter ID per instance (stable across renders)
  const instanceIdRef = useRef(0);
  useEffect(() => {
    instanceIdRef.current = ++_instanceCounter;
  }, []);
  const filterId = `wiii-glow-${instanceIdRef.current}`;

  // Animation hook (rAF skipped for tiny tier internally)
  const {
    svgRef,
    canvasRef,
    pathRef,
    faceGroupRef,
    leftEyeRef,
    rightEyeRef,
    leftIrisRef,
    rightIrisRef,
    leftBrowRef,
    rightBrowRef,
    mouthRef,
    leftBlushRef,
    rightBlushRef,
    leftHappyRef,
    rightHappyRef,
    sparkleRef,
    thoughtRef,
    sweatRef,
    musicRef,
    heartRef,
    exclaimRef,
    questionRef,
    angerVeinRef,
    gloomRef,
    spiralRef,
    flowerRef,
    zzzRef,
    fireRef,
    leftStarRef,
    rightStarRef,
    leftHeartRef,
    rightHeartRef,
    leftKORef,
    rightKORef,
    teethRef,
    tongueRef,
    mouthGlintRef,
    leftTearRef,
    rightTearRef,
    leftMoistureRef,
    rightMoistureRef,
    glowOpacity,
    glowColor: _glowColor,
    blobColor,
    scale,
    indicatorColor,
    indicatorVisible,
  } = useAvatarAnimation(state, size, mood, soulEmotion);

  const ariaLabel = STATE_LABELS[state] || "Wiii";

  // ─── Tiny Tier: CSS-only (matches Sprint 111 behavior) ─────────────
  if (tier === "tiny") {
    return (
      <motion.div
        role="img"
        aria-label={ariaLabel}
        className={`wiii-avatar wiii-avatar-tiny relative shrink-0 ${className}`}
        style={{ width: size, height: size }}
      >
        <motion.div
          className="w-full h-full flex items-center justify-center text-white font-bold overflow-hidden"
          style={{
            fontSize: Math.round(size * 0.46),
            background: config.blobColor,
            borderRadius: config.tinyBorderRadius,
            boxShadow: `0 0 ${Math.round(size * 0.5)}px ${config.glowColor}${Math.round(config.glowIntensity * 255).toString(16).padStart(2, "0")}`,
          }}
          animate={
            state === "thinking"
              ? { scale: [1, 1.06, 1] }
              : state === "idle"
                ? { scale: [1, 1.03, 1] }
                : { scale: [1.08, 1] }
          }
          transition={
            state === "thinking"
              ? { duration: 1.2, repeat: Infinity, ease: "easeInOut" }
              : state === "idle"
                ? { duration: 3, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.4, ease: "easeOut" }
          }
        >
          W
        </motion.div>
      </motion.div>
    );
  }

  // ─── Medium/Large Tier: SVG Blob + optional Canvas particles ───────
  const halfSize = size / 2;
  const glowStdDev = Math.max(1, Math.round(size * 0.08));
  const indicatorSize = Math.max(3, Math.round(size * 0.14));

  // Sprint 130: ViewBox padding to prevent glow/particle clipping
  const padPx = Math.round(size * VIEWBOX_PAD_RATIO);
  const expandedSize = size + padPx * 2;

  // Initial circle path (replaced by noise-deformed path via rAF)
  const initRadius = halfSize * 0.82;
  const initialPath = `M ${halfSize} ${halfSize - initRadius} A ${initRadius} ${initRadius} 0 1 1 ${halfSize} ${halfSize + initRadius} A ${initRadius} ${initRadius} 0 1 1 ${halfSize} ${halfSize - initRadius} Z`;

  return (
    <motion.div
      role="img"
      aria-label={ariaLabel}
      className={`wiii-avatar relative shrink-0 ${className}`}
      style={{ width: size, height: size, overflow: "visible" }}
      animate={{ scale }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      {/* Canvas layer — particles behind blob (large tier only) */}
      {tier === "large" && (
        <canvas
          ref={canvasRef as React.Ref<HTMLCanvasElement>}
          className="absolute wiii-avatar-canvas"
          style={{
            width: expandedSize,
            height: expandedSize,
            left: -padPx,
            top: -padPx,
          }}
        />
      )}

      {/* SVG layer — blob shape + glow filter + face/"W" text */}
      <svg
        ref={svgRef as React.Ref<SVGSVGElement>}
        viewBox={`${-padPx} ${-padPx} ${expandedSize} ${expandedSize}`}
        width={expandedSize}
        height={expandedSize}
        className="absolute wiii-avatar-svg"
        style={{ left: -padPx, top: -padPx }}
        aria-hidden="true"
      >
        <defs>
          <filter
            id={filterId}
            filterUnits="userSpaceOnUse"
            x={-padPx}
            y={-padPx}
            width={expandedSize}
            height={expandedSize}
          >
            <feGaussianBlur
              in="SourceGraphic"
              stdDeviation={glowStdDev}
              result="blur"
            />
            <feColorMatrix
              in="blur"
              type="matrix"
              values={`1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 ${(glowOpacity * 3).toFixed(2)} 0`}
              result="glow"
            />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Sprint 134: Error shiver — feTurbulence displacement for distress */}
          <filter
            id={`${filterId}-shiver`}
            filterUnits="userSpaceOnUse"
            x={-padPx}
            y={-padPx}
            width={expandedSize}
            height={expandedSize}
          >
            <feGaussianBlur
              in="SourceGraphic"
              stdDeviation={glowStdDev}
              result="blur"
            />
            <feColorMatrix
              in="blur"
              type="matrix"
              values={`1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 ${(glowOpacity * 3).toFixed(2)} 0`}
              result="glow"
            />
            <feTurbulence
              type="turbulence"
              baseFrequency="0.04 0.02"
              numOctaves={3}
              seed={instanceIdRef.current}
              result="noise"
            >
              <animate attributeName="seed" values="0;10;0" dur="0.4s" repeatCount="indefinite" />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="noise" scale={3} xChannelSelector="R" yChannelSelector="G" result="displaced" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="displaced" />
            </feMerge>
          </filter>
        </defs>

        {/* Blob path — updated at 60fps via direct DOM ref */}
        <path
          ref={pathRef as React.Ref<SVGPathElement>}
          fill={blobColor}
          filter={state === "error" ? `url(#${filterId}-shiver)` : glowOpacity > 0.05 ? `url(#${filterId})` : undefined}
          d={initialPath}
        />

        {/* Sprint 129: Face (large tier) or "W" character (medium tier) */}
        {tier === "large" ? (
          <FaceGroup
            halfSize={halfSize}
            blobRadius={initRadius}
            instanceId={instanceIdRef.current}
            faceGroupRef={faceGroupRef}
            leftEyeRef={leftEyeRef}
            rightEyeRef={rightEyeRef}
            leftIrisRef={leftIrisRef}
            rightIrisRef={rightIrisRef}
            leftBrowRef={leftBrowRef}
            rightBrowRef={rightBrowRef}
            mouthRef={mouthRef}
            leftBlushRef={leftBlushRef}
            rightBlushRef={rightBlushRef}
            leftHappyRef={leftHappyRef}
            rightHappyRef={rightHappyRef}
            leftStarRef={leftStarRef}
            rightStarRef={rightStarRef}
            leftHeartRef={leftHeartRef}
            rightHeartRef={rightHeartRef}
            leftKORef={leftKORef}
            rightKORef={rightKORef}
            teethRef={teethRef}
            tongueRef={tongueRef}
            mouthGlintRef={mouthGlintRef}
            leftTearRef={leftTearRef}
            rightTearRef={rightTearRef}
            leftMoistureRef={leftMoistureRef}
            rightMoistureRef={rightMoistureRef}
            state={state}
          />
        ) : (
          <text
            x={halfSize}
            y={halfSize}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            fontWeight="bold"
            fontSize={fontSize}
            style={{ pointerEvents: "none" }}
          >
            W
          </text>
        )}

        {/* Sprint 131 Phase 4: Manga indicators (large tier only) */}
        {tier === "large" && (
          <MangaIndicatorGroup
            halfSize={halfSize}
            blobRadius={initRadius}
            sparkleRef={sparkleRef}
            thoughtRef={thoughtRef}
            sweatRef={sweatRef}
            musicRef={musicRef}
            heartRef={heartRef}
            exclaimRef={exclaimRef}
            questionRef={questionRef}
            angerVeinRef={angerVeinRef}
            gloomRef={gloomRef}
            spiralRef={spiralRef}
            flowerRef={flowerRef}
            zzzRef={zzzRef}
            fireRef={fireRef}
            state={state}
          />
        )}
      </svg>

      {/* Online indicator dot */}
      {indicatorVisible && (
        <motion.div
          className="absolute rounded-full"
          style={{
            width: indicatorSize,
            height: indicatorSize,
            bottom: 0,
            right: 0,
            background: indicatorColor,
          }}
          animate={
            state === "thinking"
              ? { scale: [1, 1.3, 1], opacity: [0.8, 1, 0.8] }
              : { scale: [1, 1.2, 1] }
          }
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
    </motion.div>
  );
}

export const WiiiAvatar = memo(WiiiAvatarInner);
