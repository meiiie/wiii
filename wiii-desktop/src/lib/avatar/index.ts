/**
 * Avatar module barrel export — Sprint 115: Living Avatar Foundation.
 * Sprint 119: Added STATE_LABELS, lerpHexColor exports.
 * Sprint 129: Added face expression exports.
 * Sprint 130: Added generateHappyEyePath, springEase exports.
 * Sprint 131: Added FaceDimensions type export.
 * Sprint 141: Added Rive avatar exports.
 */
export { WiiiAvatar, STATE_LABELS } from "./WiiiAvatar";
export type { AvatarState, WiiiAvatarProps, SizeTier, StateVisuals, Particle, FaceExpression, MoodType, SoulEmotionData, ExpressionEcho } from "./types";
export type { FaceDimensions } from "./face-geometry";
export type { MoodTheme } from "./mood-theme";
export { STATE_CONFIG, getSizeTier, getBlobResolution } from "./state-config";
export { FACE_EXPRESSIONS, lerpFaceExpression, anticipateEase } from "./face-config";
export { getFaceDimensions, generateMouthPath, generateHappyEyePath, generateCatMouthPath, generateDotMouthPath, generateWavyMouthPath, generatePoutMouthPath, generateKnockedOutEyePath, generateAngerVeinPath, generateGloomLinesPath, generateSpiralPath, generateFlowerPath, generateZzzPath, generateFirePath, generateTeethPath, generateTonguePath } from "./face-geometry";
export { BlinkController } from "./blink-controller";
export { lerpHexColor, springEase } from "./use-avatar-animation";
export { getIndicatorForState, generateSparklePath, generateSweatDropPath, generateMusicNotePath, generateHeartPath, generateExclaimPath, generateQuestionPath } from "./manga-indicators";
export { REACTION_REGISTRY, computeReactionIntensity } from "./micro-reaction-registry";
export type { ReactionDef, ReactionModifier } from "./micro-reaction-registry";
export type { MangaIndicatorType, IndicatorPosition } from "./manga-indicators";
export { MOOD_THEMES, MOOD_DECAY_DURATIONS, applyMoodToExpression, applyMoodToVisuals } from "./mood-theme";
export { spawnBurst, spawnFallingBurst, updateBurstParticles, renderBurstParticles, spawnParticle, updateParticles, renderParticles } from "./particle-system";
export type { ParticleShape, BurstParticle } from "./particle-system";

// Sprint 144: New modules
export { REACTION_CHAINS, advanceChain, createChainPlayback } from "./reaction-chains";
export type { ReactionChain, ReactionChainStep, ChainPlayback } from "./reaction-chains";
export { GazeController, GAZE_TARGETS } from "./gaze-controller";
export type { GazeTarget } from "./gaze-controller";
export { updateMoisture, getMoistureEffects, generateTearDropPath, createMoistureState } from "./eye-moisture";
export type { EyeMoistureState, MoistureTriggers } from "./eye-moisture";

// Sprint 141: Rive avatar
export { RiveWiiiAvatar } from "./rive/RiveWiiiAvatar";
export type { RiveWiiiAvatarProps } from "./rive/RiveWiiiAvatar";
export { resolveAvatarState, mapToRive, mapFromRive, faceExpressionToRive, lerpRiveInputs } from "./rive/rive-adapter";
export { RIVE_INPUTS, RIVE_TRIGGERS, RIVE_BOOLEANS, RIVE_FILE_PATH, MAIN_STATE_MACHINE, PARAM_RANGES } from "./rive/rive-config";
