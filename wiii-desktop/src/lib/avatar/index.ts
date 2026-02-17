/**
 * Avatar module barrel export — Sprint 115: Living Avatar Foundation.
 * Sprint 119: Added STATE_LABELS, lerpHexColor exports.
 */
export { WiiiAvatar, STATE_LABELS } from "./WiiiAvatar";
export type { AvatarState, WiiiAvatarProps, SizeTier, StateVisuals, Particle } from "./types";
export { STATE_CONFIG, getSizeTier, getBlobResolution } from "./state-config";
export { lerpHexColor } from "./use-avatar-animation";
