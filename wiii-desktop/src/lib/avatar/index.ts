/**
 * Avatar module barrel export — Sprint 115: Living Avatar Foundation.
 * Sprint 119: Added STATE_LABELS, lerpHexColor exports.
 * Sprint 129: Added face expression exports.
 */
export { WiiiAvatar, STATE_LABELS } from "./WiiiAvatar";
export type { AvatarState, WiiiAvatarProps, SizeTier, StateVisuals, Particle, FaceExpression } from "./types";
export { STATE_CONFIG, getSizeTier, getBlobResolution } from "./state-config";
export { FACE_EXPRESSIONS, lerpFaceExpression } from "./face-config";
export { getFaceDimensions, generateMouthPath } from "./face-geometry";
export { BlinkController } from "./blink-controller";
export { lerpHexColor } from "./use-avatar-animation";
